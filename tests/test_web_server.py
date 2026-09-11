"""管理面板本地服务：REST/SSE/静态托管/token 鉴权

覆盖范围说明：core/web_server.py 原先没有任何测试，而它是管理面板的全部后端。
这里用真实 HTTP 请求打真实 ThreadingHTTPServer（端口 0 自动分配），
只把桌宠对象与数据文件路径替换掉，不 mock 网络层。
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request

import pytest

from core import config as cfg
from core import web_server as ws_mod
from core.web_server import ManagementServer


# ── 隔离：绝不碰真实 data/ 与 .env ────────
@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """把所有持久化路径指到 tmp_path。

    否则测试会覆写用户真实的 settings.json / games.json / skills_config.json / .env。
    """
    monkeypatch.setattr(cfg, "_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(ws_mod, "_MEMORY_ROUNDS_MIN", ws_mod._MEMORY_ROUNDS_MIN)
    # _apply_system 会写 cfg 全局，测试后还原
    for name in ("MIN_AUTO_REPLY", "MAX_AUTO_REPLY", "PRESET_MIN_INTERVAL",
                 "PRESET_MAX_INTERVAL", "MEMORY_CONTEXT_SIZE"):
        monkeypatch.setattr(cfg, name, getattr(cfg, name))
    # API 设置：不读写真实 .env
    monkeypatch.setattr(ws_mod, "load_api_settings",
                        lambda: {"provider": "deepseek", "model": "deepseek-chat",
                                 "api_key": "sk-" + "x" * 20})
    saved = {}
    monkeypatch.setattr(ws_mod, "save_api_settings",
                        lambda p, m, k: saved.update(provider=p, model=m, key=k))
    monkeypatch.setattr(ws_mod, "test_connection", lambda p, k, m: (True, "连接成功"))
    return tmp_path


# ── 假桌宠 ──────────────────────────────
class FakeChatHistory:
    def __init__(self):
        self.history = [
            {"role": "user", "content": "今天天气怎么样", "timestamp": "2026-01-01 10:00:00"},
            {"role": "assistant", "content": "是个跑步的好天气", "timestamp": "2026-01-01 10:00:05"},
        ]
        self.stats = {"total_messages": 2, "last_updated": "2026-01-01 10:00:05"}

    def get_context(self, size=100):
        return list(self.history[-size:])

    def add(self, role, content):
        self.history.append({"role": role, "content": content, "timestamp": "t"})

    def search(self, kw):
        # 与 ChatHistoryManager.search 一致：同时匹配正文与时间戳
        kw = kw.lower()
        return [m for m in self.history
                if kw in m["content"].lower() or kw in m["timestamp"].lower()]

    def clear(self):
        self.history = []


class FakeStatus:
    hunger_pct = 80.0
    energy_pct = 60.0

    def __init__(self):
        self.fed = 0

    def feed(self):
        self.fed += 1


class FakeAI:
    is_configured = True

    def __init__(self):
        self.switched = None

    def ask(self, prompt, with_screenshot=False, history_context=None,
            tools=None, execute_tool=None):
        return "小栗帽收到啦", ""

    def switch(self, provider, model, key):
        self.switched = (provider, model, key)


class FakeSkillManager:
    def __init__(self):
        self.toggled = []

    def list_skills(self):
        return [
            {"name": "weather", "description": "查天气", "enabled": True, "dirname": "weather"},
            {"name": "schedule", "description": "安排表", "enabled": False, "dirname": "schedule"},
        ]

    def get_skill_detail(self, name):
        for s in self.list_skills():
            if s["name"] == name:
                return dict(s, parameters=[{"name": "city", "type": "string",
                                            "required": True, "description": "城市"}])
        return None

    def get_tools(self):
        return []

    def execute(self, name, arguments="{}"):
        return f"{name} 执行结果"

    def toggle(self, name, enabled):
        self.toggled.append((name, enabled))

    def remove_skill(self, name):
        return name == "weather"

    def add_skill(self, path):
        return True, "添加成功"

    def add_skill_zip(self, path):
        return True, "压缩包添加成功"


class FakeGameManager:
    def __init__(self):
        self.enabled = {"fly_high": True, "fishing": False}
        self._active = None
        self.started = []
        self.stopped = 0

    def list_all(self):
        from game import GAMES
        return [(k, v["name"], self.enabled.get(k, True)) for k, v in GAMES.items()]

    def is_active(self):
        return self._active is not None

    def set_enabled(self, key, enabled):
        self.enabled[key] = enabled

    def start(self, key):
        self.started.append(key)
        self._active = key

    def stop(self):
        self.stopped += 1
        self._active = None


class FakeRoot:
    """把 after 立即执行，模拟 Tk 主线程。"""

    def __init__(self):
        self.scheduled = []

    def after(self, delay, func=None, *args):
        self.scheduled.append((delay, func))
        if func is not None:
            func(*args)
        return "after#1"


class FakePet:
    def __init__(self):
        self.status = FakeStatus()
        self.chat_history = FakeChatHistory()
        self.ai = FakeAI()
        self.skill_manager = FakeSkillManager()
        self.game_manager = FakeGameManager()
        self.root = FakeRoot()
        self.start_time = 1_000_000.0
        self.min_auto_reply_time = 60
        self.max_auto_reply_time = 300
        self.preset_min_interval = 120
        self.preset_max_interval = 600
        self.scale_factor = 1.0
        self.min_scale = 0.5
        self.max_scale = 2.0
        self.resized = []
        self.restarted = 0
        self.quit_called = 0

    def _resize_pet(self, scale):
        self.resized.append(scale)
        self.scale_factor = scale

    def restart(self):
        self.restarted += 1

    def quit(self):
        self.quit_called += 1

    def _handle_ai_response(self, text):
        self.last_response = text


# ── 服务 fixture ────────────────────────
@pytest.fixture
def server(tmp_path):
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html><body>panel</body></html>", encoding="utf-8")
    (static / "app.js").write_text("console.log(1)", encoding="utf-8")
    s = ManagementServer(FakePet(), static_dir=str(static), port=0)
    assert s.start() is True
    try:
        yield s
    finally:
        s.stop()


class Client:
    """极简 HTTP 客户端，带 token 与 JSON 便捷方法。"""

    def __init__(self, server: ManagementServer, token: str | None = None):
        self.base = f"http://127.0.0.1:{server.port}"
        self.token = server.token if token is None else token

    def request(self, method, path, body=None, headers=None, auth=True):
        url = self.base + path
        data = None
        hdrs = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        if auth and self.token:
            hdrs["X-Management-Token"] = self.token
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return resp.status, raw
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def json(self, method, path, body=None, auth=True):
        code, raw = self.request(method, path, body, auth=auth)
        try:
            return code, json.loads(raw.decode("utf-8"))
        except Exception:
            return code, None


@pytest.fixture
def client(server):
    return Client(server)


# ── 生命周期 ────────────────────────────
def test_start_assigns_ephemeral_port(server):
    assert server.port > 0
    assert server.url().startswith(f"http://127.0.0.1:{server.port}/?token=")


def test_start_is_idempotent(server):
    port = server.port
    assert server.start() is True
    assert server.port == port, "重复 start() 不应重新绑定端口"


def test_token_is_random_per_instance(tmp_path):
    a = ManagementServer(FakePet(), static_dir=str(tmp_path), port=0)
    b = ManagementServer(FakePet(), static_dir=str(tmp_path), port=0)
    assert len(a.token) >= 16
    assert a.token != b.token


def test_stop_is_safe_to_call_twice(server):
    server.stop()
    server.stop()  # 不应抛异常


# ── 鉴权 ────────────────────────────────
def test_api_requires_token(client):
    code, _ = client.request("GET", "/api/status", auth=False)
    assert code == 401


def test_wrong_token_rejected(client):
    code, _ = client.request("GET", "/api/status",
                             headers={"X-Management-Token": "wrong"}, auth=False)
    assert code == 401


def test_token_via_query_is_accepted(server):
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.port}/api/status?token={server.token}", timeout=10
    ) as resp:
        assert resp.status == 200
        assert b"hunger" in resp.read()


def test_static_does_not_require_token(client):
    code, raw = client.request("GET", "/", auth=False)
    assert code == 200
    assert b"panel" in raw


# ── /api/status ─────────────────────────
def test_status_payload_shape(client):
    code, data = client.json("GET", "/api/status")
    assert code == 200
    for key in ("hunger", "energy", "chatRounds", "uptimeSec", "enabledSkills",
                "totalSkills", "sysCpu", "sysMemMB", "petOnline"):
        assert key in data, f"缺少字段 {key}"
    assert data["hunger"] == 80.0
    assert data["energy"] == 60.0
    assert data["totalSkills"] == 2
    assert data["enabledSkills"] == 1  # 只有一个 enabled=True


def test_status_counts_chat_rounds(server):
    server.pet.chat_history.stats["total_messages"] = 7
    _, data = Client(server).json("GET", "/api/status")
    assert data["chatRounds"] == 3  # 7 // 2


def test_status_survives_pet_missing_attrs(tmp_path):
    class Bare:
        pass

    s = ManagementServer(Bare(), static_dir=str(tmp_path), port=0)
    assert s.start() is True
    try:
        payload = s.status_payload()
        assert payload["hunger"] == 50.0
        assert payload["petOnline"] is True
    finally:
        s.stop()


# ── /api/pet/feed ───────────────────────
def test_feed_calls_status_feed(client, server):
    code, data = client.json("POST", "/api/pet/feed", {})
    assert code == 200
    assert server.pet.status.fed == 1
    assert data["hunger"] == 80.0


# ── /api/chat ───────────────────────────
def test_chat_appends_history(client, server):
    code, data = client.json("POST", "/api/chat", {"text": "你好"})
    assert code == 200
    assert data["reply"] == "小栗帽收到啦"
    roles = [m["role"] for m in server.pet.chat_history.history[-2:]]
    assert roles == ["user", "assistant"]


def test_chat_rejects_empty(client, server):
    code, _ = client.json("POST", "/api/chat", {"text": "   "})
    assert code == 400
    assert len(server.pet.chat_history.history) == 2, "空消息不应写入历史"


# ── /api/history ────────────────────────
def test_history_returns_messages(client):
    code, data = client.json("GET", "/api/history")
    assert code == 200
    assert len(data["messages"]) == 2


def test_history_search_filters(client):
    from urllib.parse import quote

    code, data = client.json("GET", f"/api/history?q={quote('天气')}")
    assert code == 200
    assert len(data["messages"]) == 2
    code, data = client.json("GET", f"/api/history?q={quote('不存在')}")
    assert data["messages"] == []


def test_history_search_matches_timestamp(client):
    from urllib.parse import quote

    _, data = client.json("GET", f"/api/history?q={quote('2026-01-01')}")
    assert len(data["messages"]) == 2


def test_history_delete_clears(client, server):
    code, data = client.json("DELETE", "/api/history")
    assert code == 200 and data["ok"] is True
    assert server.pet.chat_history.history == []


def test_history_export_is_text_attachment(client):
    code, raw = client.request("GET", "/api/history/export")
    assert code == 200
    text = raw.decode("utf-8")
    assert "小栗帽聊天记录导出" in text
    assert "训练员: 今天天气怎么样" in text
    assert "小栗帽: 是个跑步的好天气" in text


def test_history_delete_requires_token(client):
    code, _ = client.request("DELETE", "/api/history", auth=False)
    assert code == 401


# ── /api/settings ───────────────────────
def test_settings_payload_structure(client):
    code, data = client.json("GET", "/api/settings")
    assert code == 200
    for section in ("api", "system", "font", "pet"):
        assert section in data
    assert data["api"]["provider"] == "deepseek"
    assert data["api"]["keyConfigured"] is True
    assert data["api"]["providers"], "应下发厂商列表"
    for p in data["api"]["providers"]:
        assert {"key", "name", "models"} <= set(p)


def test_settings_memory_rounds_bounds_are_downloaded(client):
    """区间与默认值必须由后端下发，前端不得硬编码（回归点）。"""
    _, data = client.json("GET", "/api/settings")
    sysinfo = data["system"]
    assert sysinfo["memoryRoundsMin"] == 5
    assert sysinfo["memoryRoundsMax"] == 250
    assert sysinfo["memoryRoundsDefault"] == cfg.DEFAULT_MEMORY_CONTEXT_SIZE // 2


# ── /api/settings/system ────────────────
def test_system_settings_applied_and_persisted(client, server, tmp_path):
    code, _ = client.json("POST", "/api/settings/system",
                          {"minAutoReply": 30, "maxAutoReply": 90,
                           "presetMin": 60, "presetMax": 120, "memoryRounds": 50})
    assert code == 200
    assert server.pet.min_auto_reply_time == 30
    assert server.pet.max_auto_reply_time == 90
    assert cfg.MEMORY_CONTEXT_SIZE == 100  # 50 轮 = 100 条
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["min_auto_reply"] == 30
    assert saved["memory_context_size"] == 100


def test_system_rejects_inverted_intervals(client):
    code, data = client.json("POST", "/api/settings/system",
                             {"minAutoReply": 300, "maxAutoReply": 60})
    assert code == 400
    assert "最短间隔" in data["error"]


def test_system_rejects_out_of_range_memory_rounds(client):
    for bad in (3, 0, -1, 600):
        code, data = client.json("POST", "/api/settings/system", {"memoryRounds": bad})
        assert code == 400, f"memoryRounds={bad} 应被拒绝而不是静默钳制"
        assert "记忆轮数" in data["error"]


def test_system_accepts_boundary_memory_rounds(client):
    for ok in (5, 250):
        code, _ = client.json("POST", "/api/settings/system", {"memoryRounds": ok})
        assert code == 200, f"memoryRounds={ok} 是合法边界值"


def test_partial_system_update_keeps_other_values(client, server):
    """记忆卡片只发 memoryRounds，其余三项不应被重置。"""
    server.pet.preset_min_interval = 111
    server.pet.preset_max_interval = 222
    code, _ = client.json("POST", "/api/settings/system", {"memoryRounds": 40})
    assert code == 200
    assert server.pet.preset_min_interval == 111
    assert server.pet.preset_max_interval == 222


# ── /api/pet/size ───────────────────────
def test_pet_size_clamped_and_reported(client, server, tmp_path):
    code, data = client.json("POST", "/api/pet/size", {"scale": 9.9})
    assert code == 200
    assert data["scale"] == 2.0, "应回传钳制后的实际值"
    assert server.pet.resized == [2.0]
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["scale"] == 2.0, "缩放必须落盘，否则重启回 100%"


def test_pet_size_lower_bound(client):
    code, data = client.json("POST", "/api/pet/size", {"scale": 0.1})
    assert code == 200 and data["scale"] == 0.5


# ── /api/settings/font ──────────────────
def test_font_applied_and_persisted(client, tmp_path):
    code, data = client.json("POST", "/api/settings/font",
                             {"family": "SimSun", "size": 16})
    assert code == 200
    assert data["size"] == 16
    assert cfg.FONT_FAMILY == "SimSun"
    assert cfg.FONT_SIZE == 16
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["font_family"] == "SimSun"
    assert saved["font_size"] == 16


def test_font_size_clamped(client):
    _, data = client.json("POST", "/api/settings/font", {"family": "SimSun", "size": 999})
    assert data["size"] == cfg.FONT_SIZE_MAX


def test_font_rejects_garbage_size(client):
    code, data = client.json("POST", "/api/settings/font", {"family": "SimSun", "size": "big"})
    assert code == 400
    assert "字号" in data["error"]


# ── /api/settings/api ───────────────────
def test_save_api_settings_switches_client(client, server):
    code, _ = client.json("POST", "/api/settings/api",
                          {"provider": "openai", "model": "gpt-4o",
                           "apiKey": "sk-" + "y" * 20})
    assert code == 200
    assert server.pet.ai.switched == ("openai", "gpt-4o", "sk-" + "y" * 20)


def test_save_api_rejects_short_key(client):
    code, data = client.json("POST", "/api/settings/api",
                             {"provider": "openai", "model": "gpt-4o", "apiKey": "short"})
    assert code == 400
    assert "太短" in data["error"]


def test_test_connection_endpoint(client):
    code, data = client.json("POST", "/api/settings/api/test",
                             {"provider": "openai", "model": "gpt-4o",
                              "apiKey": "sk-" + "y" * 20})
    assert code == 200
    assert data["ok"] is True and data["message"] == "连接成功"


# ── 进程控制：必须离开 HTTP 线程 ─────────
def wait_for(predicate, timeout=5.0):
    """服务端先回响应、再执行 root.after，因此断言前必须等状态落定。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_restart_is_scheduled_on_tk_thread(client, server):
    code, _ = client.json("POST", "/api/pet/restart", {})
    assert code == 200
    assert wait_for(lambda: server.pet.restarted == 1), "重启必须转发到 Tk 线程执行"
    delays = [d for d, _ in server.pet.root.scheduled]
    assert delays, "重启必须通过 root.after 转发，而不是在 HTTP 线程里直接调用"


def test_restart_delay_is_nonzero(client, server):
    client.json("POST", "/api/pet/restart", {})
    assert wait_for(lambda: bool(server.pet.root.scheduled))
    assert server.pet.root.scheduled[0][0] > 0


def test_quit_is_scheduled_on_tk_thread(client, server):
    code, _ = client.json("POST", "/api/pet/quit", {})
    assert code == 200
    assert wait_for(lambda: server.pet.quit_called == 1), "退出必须转发到 Tk 线程执行"
    delays = [d for d, _ in server.pet.root.scheduled]
    assert delays, "退出必须通过 root.after 转发，而不是在 HTTP 线程里直接调用"


# ── /api/games ──────────────────────────
def test_games_payload(client):
    code, data = client.json("GET", "/api/games")
    assert code == 200
    assert len(data["games"]) == 5
    assert data["active"] is None
    for g in data["games"]:
        assert {"key", "name", "desc", "enabled", "active"} <= set(g)


def test_game_toggle(client, server):
    code, data = client.json("POST", "/api/games/fly_high/toggle", {"enabled": False})
    assert code == 200
    assert server.pet.game_manager.enabled["fly_high"] is False
    assert next(g for g in data["games"] if g["key"] == "fly_high")["enabled"] is False


def test_game_start_scheduled_on_tk_thread_and_optimistically_reported(client, server):
    code, data = client.json("POST", "/api/games/fly_high/start", {})
    assert code == 200
    # 必须经 root.after 转发，不能在 HTTP 线程里直接创建 Toplevel
    assert any(d == 50 for d, _ in server.pet.root.scheduled)
    assert server.pet.game_manager.started == ["fly_high"]
    assert data["active"] == "一飞冲天"
    assert next(g for g in data["games"] if g["key"] == "fly_high")["active"] is True


def test_game_stop_reports_cleared_active(client, server):
    client.json("POST", "/api/games/dash_run/start", {})
    code, data = client.json("POST", "/api/games/stop", {})
    assert code == 200
    assert data["active"] is None
    assert all(g["active"] is False for g in data["games"])
    assert server.pet.game_manager.stopped >= 1


def test_game_optimistic_active_does_not_leak_to_other_games(client):
    _, data = client.json("POST", "/api/games/fishing/start", {})
    active = [g["key"] for g in data["games"] if g["active"]]
    assert active == ["fishing"], "只应把请求的游戏标为 active"


# ── /api/skills ─────────────────────────
def test_skills_list(client):
    code, data = client.json("GET", "/api/skills")
    assert code == 200
    assert {s["name"] for s in data["skills"]} == {"weather", "schedule"}


def test_skill_detail_includes_parameters_and_md(client, server, tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: weather\n---\n\n正文", encoding="utf-8")
    monkeypatch.setattr("core.skill_system.manager.SKILLS_DIR", str(tmp_path / "skills"))

    code, data = client.json("GET", "/api/skills/weather")
    assert code == 200
    assert data["parameters"][0]["name"] == "city"
    assert "name: weather" in data["skillMd"]


def test_skill_detail_404(client):
    code, _ = client.json("GET", "/api/skills/nope")
    assert code == 404


def test_skill_toggle(client, server):
    code, _ = client.json("POST", "/api/skills/weather/toggle", {"enabled": False})
    assert code == 200
    assert server.pet.skill_manager.toggled == [("weather", False)]


def test_skill_execute(client):
    code, data = client.json("POST", "/api/skills/weather/execute",
                             {"arguments": {"city": "深圳"}})
    assert code == 200
    assert data["result"] == "weather 执行结果"


def test_skill_delete(client):
    code, data = client.json("DELETE", "/api/skills/weather")
    assert code == 200 and data["ok"] is True
    code, data = client.json("DELETE", "/api/skills/schedule")
    assert code == 200 and data["ok"] is False


def test_skill_import_py(client, server):
    payload = base64.b64encode(b"def execute():\n    return 'ok'\n").decode()
    code, data = client.json("POST", "/api/skills/import",
                             {"filename": "demo.py", "content": payload})
    assert code == 200 and data["ok"] is True
    assert not os.path.exists(os.path.join(os.environ.get("TEMP", "."), "demo.py"))


def test_skill_import_rejects_missing_fields(client):
    code, data = client.json("POST", "/api/skills/import", {"filename": "demo.py"})
    assert code == 400
    assert "缺少文件" in data["error"]


def test_skill_import_cleans_up_temp_file(client, server, monkeypatch):
    """导入失败时临时文件也必须删除。"""
    captured = {}

    def fake_add(path):
        captured["path"] = path
        captured["existed"] = os.path.isfile(path)
        return False, "模拟失败"

    monkeypatch.setattr(server.pet.skill_manager, "add_skill", fake_add)
    payload = base64.b64encode(b"x = 1\n").decode()
    code, data = client.json("POST", "/api/skills/import",
                             {"filename": "demo.py", "content": payload})
    assert code == 200 and data["ok"] is False
    assert captured["existed"] is True
    assert not os.path.exists(captured["path"]), "临时文件必须被清理"


# ── 静态托管 ────────────────────────────
def test_serves_index_at_root(client):
    code, raw = client.request("GET", "/")
    assert code == 200 and b"panel" in raw


def test_serves_asset_with_content_type(client):
    code, raw = client.request("GET", "/app.js")
    assert code == 200
    assert b"console.log" in raw


def test_missing_static_returns_503_with_hint(tmp_path):
    s = ManagementServer(FakePet(), static_dir=str(tmp_path / "not-built"), port=0)
    s.start()
    try:
        c = Client(s)
        code, data = c.json("GET", "/")
        assert code == 503
        assert "npm run build" in data["hint"]
    finally:
        s.stop()


def test_unknown_api_route_404(client):
    code, _ = client.json("GET", "/api/nope")
    assert code == 404


def test_unknown_post_route_404(client):
    code, _ = client.json("POST", "/api/nope", {})
    assert code == 404


# ── 日志读取 ────────────────────────────
def test_log_tail_reads_last_lines(server, tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "kurumi.log"
    log_file.write_text("\n".join(f"line-{i}" for i in range(1, 51)), encoding="utf-8")
    monkeypatch.setattr(server, "_log_file_path", lambda: str(log_file))

    lines = server._read_log_tail(10)
    assert lines == [f"line-{i}" for i in range(41, 51)]


def test_log_tail_missing_file(server, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_log_file_path", lambda: str(tmp_path / "nope.log"))
    assert server._read_log_tail(10) == []


def test_log_new_returns_only_appended_bytes(server, tmp_path, monkeypatch):
    log_file = tmp_path / "k.log"
    log_file.write_text("a\nb\n", encoding="utf-8")
    monkeypatch.setattr(server, "_log_file_path", lambda: str(log_file))

    offset = server._log_offset()
    lines, new_offset = server._read_log_new(offset)
    assert lines == [] and new_offset == offset

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("c\n")
    lines, new_offset = server._read_log_new(offset)
    assert lines == ["c"] and new_offset > offset


# ── 并发 ────────────────────────────────
def test_concurrent_requests(server):
    """ThreadingHTTPServer 必须能并发处理，不应相互阻塞。"""
    results = []

    def hit():
        c = Client(server)
        code, data = c.json("GET", "/api/status")
        results.append((code, data is not None))

    threads = [threading.Thread(target=hit) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    assert len(results) == 8
    assert all(code == 200 for code, _ in results)
