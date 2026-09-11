"""管理面板本地服务：托管 web/dist + REST API + SSE 实时推送。

- 仅监听 127.0.0.1
- 每次启动生成随机 token；API 请求须携带 token（query 或 X-Management-Token 头）
- 静态页与 API 同源，无 CORS 问题
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import secrets
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

from core import config as cfg
from core.ai_providers import (
    get_models,
    get_provider_list,
    load_api_settings,
    save_api_settings,
    test_connection,
)
from core.paths import get_log_dir, get_resource_path
from utils.logger import get_logger

log = get_logger("web_server")

DEFAULT_POLL_INTERVAL = 5.0


def mf_max() -> int:
    """长期记忆条数上限（供面板展示）。"""
    try:
        from core.memory_facts import MAX_FACTS

        return MAX_FACTS
    except Exception:
        return 40


def _autostart_enabled() -> bool:
    try:
        from core.autostart import is_enabled

        return is_enabled()
    except Exception:
        return False


def _data_dir() -> str:
    try:
        from core.paths import resolve_data_dir

        return resolve_data_dir()
    except Exception:
        return ""

# BaseServer.shutdown() 会等到 serve_forever 的 select 轮询返回为止，
# 标准库默认 0.5s → 每次停服白等半秒（重启/退出以及测试里都能感觉到）。
# 调小轮询间隔，停服与退出立刻返回。
_SERVE_POLL_INTERVAL = 0.05
# 记忆轮数的合法区间（轮 = 一问一答，对应 MEMORY_CONTEXT_SIZE 的 2 倍）
_MEMORY_ROUNDS_MIN = 5
_MEMORY_ROUNDS_MAX = 250
FONT_FALLBACK = [
    "Microsoft YaHei", "SimSun", "SimHei", "KaiTi", "FangSong",
    "DengXian", "NSimSun", "YouYuan", "Microsoft JhengHei",
]


class _FastShutdownHTTPServer(ThreadingHTTPServer):
    """把 serve_forever 的轮询间隔调小，使 shutdown() 立即返回。"""

    daemon_threads = True

    def serve_forever(self, poll_interval: float = _SERVE_POLL_INTERVAL) -> None:
        super().serve_forever(poll_interval)


class ManagementServer:
    """管理面板本地服务。pet 需提供 status / chat_history / skill_manager / ai 等属性。"""

    def __init__(
        self,
        pet: Any,
        static_dir: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 0,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.pet = pet
        self.static_dir = static_dir or get_resource_path("web/dist")
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        self.token = secrets.token_urlsafe(16)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ---------- 生命周期 ----------
    def start(self) -> bool:
        if self._httpd:
            return True
        try:
            httpd = _FastShutdownHTTPServer((self.host, self.port), self._make_handler())
        except OSError as e:
            log.warning("管理面板服务启动失败: %s", e)
            return False
        self.port = httpd.server_address[1]
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="mgmt-web")
        self._thread.start()
        log.info("管理面板已启动: %s", self.url())
        return True

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass

    def url(self) -> str:
        return f"http://{self.host}:{self.port}/?token={self.token}"

    # ---------- 数据 ----------
    def status_payload(self) -> Dict[str, Any]:
        p = self.pet
        payload: Dict[str, Any] = {
            "hunger": 50.0,
            "energy": 50.0,
            "chatRounds": 0,
            "uptimeSec": 0,
            "enabledSkills": 0,
            "totalSkills": 0,
            "sysCpu": None,
            "sysMemMB": None,
            "petOnline": True,
        }
        try:
            status = getattr(p, "status", None)
            if status is not None:
                payload["hunger"] = round(float(getattr(status, "hunger_pct", 50.0)), 1)
                payload["energy"] = round(float(getattr(status, "energy_pct", 50.0)), 1)
        except Exception:
            pass
        try:
            start_time = getattr(p, "start_time", None)
            if start_time:
                payload["uptimeSec"] = int(max(0, time.time() - start_time))
        except Exception:
            pass
        try:
            ch = getattr(p, "chat_history", None)
            if ch is not None:
                stats = getattr(ch, "stats", {}) or {}
                total = int(stats.get("total_messages") or 0)
                payload["chatRounds"] = total // 2
        except Exception:
            pass
        try:
            sm = getattr(p, "skill_manager", None)
            if sm is not None and hasattr(sm, "list_skills"):
                skills = sm.list_skills()
                payload["totalSkills"] = len(skills)
                payload["enabledSkills"] = sum(1 for s in skills if s.get("enabled"))
        except Exception:
            pass
        try:
            import psutil  # type: ignore

            payload["sysCpu"] = round(float(psutil.cpu_percent(interval=None)), 1)
            payload["sysMemMB"] = round(psutil.Process(os.getpid()).memory_info().rss / 1048576, 1)
        except Exception:
            pass
        payload.update(self._companion_payload())
        return payload

    def _companion_payload(self) -> Dict[str, Any]:
        """陪伴统计（跨会话累积）。缺失时返回 None，前端据此隐藏区块。"""
        c = getattr(self.pet, "companion", None)
        if c is None or not hasattr(c, "snapshot"):
            return {"companion": None}
        try:
            snap = c.snapshot()
            return {
                "companion": {
                    "daysTogether": c.days_together(),
                    "totalHours": round(snap.get("total_seconds", 0.0) / 3600.0, 1),
                    "sessionSeconds": round(snap.get("current_session_seconds", 0.0), 0),
                    "sessions": snap.get("sessions", 0),
                    "feedCount": snap.get("feed_count", 0),
                    "chatRounds": snap.get("chat_rounds", 0),
                    "dragCount": snap.get("drag_count", 0),
                    "maxFlyMeters": round(snap.get("max_fly_meters", 0.0), 1),
                    "gamesPlayed": snap.get("games_played", 0),
                    "factsLearned": snap.get("facts_learned", 0),
                }
            }
        except Exception:
            log.exception("陪伴统计读取失败")
            return {"companion": None}

    def _settings_payload(self) -> Dict[str, Any]:
        p = self.pet
        api = load_api_settings()
        providers = [
            {"key": k, "name": n, "models": get_models(k)}
            for k, n in get_provider_list()
        ]
        return {
            "api": {
                "provider": api["provider"],
                "model": api["model"],
                "keyConfigured": bool(api["api_key"] and len(api["api_key"]) > 10),
                "providers": providers,
                "models": get_models(api["provider"]),
            },
            "system": {
                "minAutoReply": int(getattr(p, "min_auto_reply_time", cfg.MIN_AUTO_REPLY)),
                "maxAutoReply": int(getattr(p, "max_auto_reply_time", cfg.MAX_AUTO_REPLY)),
                "presetMin": int(getattr(p, "preset_min_interval", cfg.PRESET_MIN_INTERVAL)),
                "presetMax": int(getattr(p, "preset_max_interval", cfg.PRESET_MAX_INTERVAL)),
                "memoryRounds": cfg.MEMORY_CONTEXT_SIZE // 2,
                # 区间与默认值由后端下发，避免前端硬编码后与 _apply_system 的钳制范围漂移
                "memoryRoundsMin": _MEMORY_ROUNDS_MIN,
                "memoryRoundsMax": _MEMORY_ROUNDS_MAX,
                "memoryRoundsDefault": cfg.DEFAULT_MEMORY_CONTEXT_SIZE // 2,
            },
            "font": {
                "family": cfg.FONT_FAMILY,
                "size": cfg.FONT_SIZE,
                "sizeMin": cfg.FONT_SIZE_MIN,
                "sizeMax": cfg.FONT_SIZE_MAX,
                "families": self._font_families(),
            },
            "pet": {
                "scale": float(getattr(p, "scale_factor", 1.0)),
                "minScale": float(getattr(p, "min_scale", cfg.MIN_SCALE)),
                "maxScale": float(getattr(p, "max_scale", cfg.MAX_SCALE)),
            },
            "systemExtra": {
                "autostart": _autostart_enabled(),
                "autostartSupported": os.name == "nt",
                "dataDir": _data_dir(),
            },
        }

    def _font_families(self) -> List[str]:
        try:
            import tkinter.font as tkfont

            root = getattr(self.pet, "root", None)
            fams = set(tkfont.families(root) if root is not None else FONT_FALLBACK)
            extra = [
                f for f in fams
                if any(k in f.lower() for k in (
                    "yahei", "simsun", "simhei", "kaiti", "fangsong", "dengxian",
                    "noto", "sarasa", "han", "cjk", "ming", "gothic", "wenquan",
                    "puhui", "zcool", "source", "serif", "sans",
                ))
            ]
            return list(dict.fromkeys(FONT_FALLBACK + sorted(extra)))
        except Exception:
            return list(FONT_FALLBACK)

    def _chat_reply(self, text: str) -> str:
        p = self.pet
        ctx = p.chat_history.get_context(cfg.MEMORY_CONTEXT_SIZE)
        text = (text or "").strip()
        if text:
            p.chat_history.add("user", text)
        r, _ = p.ai.ask(
            text or "看看屏幕",
            False,
            history_context=ctx,
            tools=p.skill_manager.get_tools(),
            execute_tool=p.skill_manager.execute,
        )
        p.chat_history.add("assistant", r)
        try:
            root = getattr(p, "root", None)
            if root is not None and hasattr(p, "_handle_ai_response"):
                root.after(0, lambda: p._handle_ai_response(r))
        except Exception:
            pass
        return r

    def _apply_system(self, data: Dict[str, Any]) -> None:
        p = self.pet
        mi = int(data.get("minAutoReply", getattr(p, "min_auto_reply_time", cfg.MIN_AUTO_REPLY)))
        ma = int(data.get("maxAutoReply", getattr(p, "max_auto_reply_time", cfg.MAX_AUTO_REPLY)))
        pr_min = int(data.get("presetMin", getattr(p, "preset_min_interval", cfg.PRESET_MIN_INTERVAL)))
        pr_max = int(data.get("presetMax", getattr(p, "preset_max_interval", cfg.PRESET_MAX_INTERVAL)))
        mem = int(data.get("memoryRounds", cfg.MEMORY_CONTEXT_SIZE // 2))
        if mi > ma or pr_min > pr_max:
            raise ValueError("最短间隔不能大于最长间隔")
        if not (_MEMORY_ROUNDS_MIN <= mem <= _MEMORY_ROUNDS_MAX):
            raise ValueError(
                f"记忆轮数需在 {_MEMORY_ROUNDS_MIN}–{_MEMORY_ROUNDS_MAX} 之间"
            )
        p.min_auto_reply_time = mi
        p.max_auto_reply_time = ma
        p.preset_min_interval = pr_min
        p.preset_max_interval = pr_max
        cfg.MIN_AUTO_REPLY = mi
        cfg.MAX_AUTO_REPLY = ma
        cfg.PRESET_MIN_INTERVAL = pr_min
        cfg.PRESET_MAX_INTERVAL = pr_max
        cfg.MEMORY_CONTEXT_SIZE = mem * 2
        cfg._save()

    def _export_text(self) -> str:
        lines = ["小栗帽聊天记录导出", "=" * 50, ""]
        for m in self.pet.chat_history.history:
            who = "训练员" if m["role"] == "user" else "小栗帽"
            lines.append(f"[{m['timestamp']}] {who}: {m['content']}")
            lines.append("")
        return "\n".join(lines)

    # ---------- 游戏 / 技能 ----------
    def _facts_payload(self) -> Dict[str, Any]:
        mf = getattr(self.pet, "memory_facts", None)
        if mf is None:
            return {"enabled": False, "facts": [], "available": False}
        try:
            return {
                "available": True,
                "enabled": bool(mf.enabled),
                "facts": mf.list_all(),
                "maxFacts": mf_max(),
            }
        except Exception:
            log.exception("长期记忆读取失败")
            return {"available": False, "enabled": False, "facts": []}

    def _games_payload(self, active_key: Optional[str] = None,
                       clear_active: bool = False) -> Dict[str, Any]:
        """active_key/clear_active 用于「已排到 Tk 线程但尚未执行」时的乐观回显。"""
        p = self.pet
        gm = getattr(p, "game_manager", None)
        games: List[Dict[str, Any]] = []
        active: Optional[str] = None
        if gm is not None and hasattr(gm, "list_all"):
            for key, name, enabled in gm.list_all():
                desc = ""
                try:
                    from game import GAMES  # type: ignore

                    desc = str(GAMES.get(key, {}).get("desc", ""))
                except Exception:
                    pass
                games.append({
                    "key": key, "name": name, "desc": desc,
                    "enabled": bool(enabled), "active": False,
                })
            try:
                if gm.is_active():
                    act = getattr(gm, "_active", None)
                    active = getattr(act, "NAME", None)
                    for g in games:
                        if active and g["name"] == active:
                            g["active"] = True
            except Exception:
                pass
        if clear_active:
            active = None
            for g in games:
                g["active"] = False
        elif active_key:
            target = next((g for g in games if g["key"] == active_key), None)
            if target is not None:
                active = target["name"]
                for g in games:
                    g["active"] = g["key"] == active_key
        return {"games": games, "active": active}

    def _skills_payload(self) -> Dict[str, Any]:
        p = self.pet
        sm = getattr(p, "skill_manager", None)
        if sm is None or not hasattr(sm, "list_skills"):
            return {"skills": []}
        return {"skills": sm.list_skills()}

    def _skill_detail(self, name: str) -> Optional[Dict[str, Any]]:
        p = self.pet
        sm = getattr(p, "skill_manager", None)
        if sm is None or not hasattr(sm, "get_skill_detail"):
            return None
        detail = sm.get_skill_detail(name)
        if detail is None:
            return None
        md = ""
        try:
            from core.skill_system.manager import SKILLS_DIR

            path = os.path.join(SKILLS_DIR, detail["dirname"], "SKILL.md")
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    md = f.read()
        except Exception:
            md = ""
        detail["skillMd"] = md
        return detail

    # ---------- HTTP ----------
    def _make_handler(self) -> type:
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "OguriMgmt/0.1"

            def do_GET(self) -> None:  # noqa: N802
                server._handle_get(self)

            def do_POST(self) -> None:  # noqa: N802
                server._handle_post(self)

            def do_DELETE(self) -> None:  # noqa: N802
                server._handle_delete(self)

            def handle_one_request(self) -> None:
                # 客户端提前断开（如 SSE 中断）后框架仍会 flush 已关闭的 wfile，
                # 抛 ValueError/BrokenPipe 属正常情况，静默忽略
                try:
                    super().handle_one_request()
                except (ValueError, BrokenPipeError, ConnectionResetError,
                        ConnectionAbortedError, TimeoutError):
                    pass

            def log_message(self, *args: Any) -> None:
                pass

        return Handler

    def _check_token(self, handler: BaseHTTPRequestHandler) -> bool:
        q = parse_qs(urlparse(handler.path).query)
        tok = (q.get("token", [""])[0] or "").strip()
        if not tok:
            tok = (handler.headers.get("X-Management-Token") or "").strip()
        return bool(tok) and secrets.compare_digest(tok, self.token)

    def _send_json(self, handler: BaseHTTPRequestHandler, code: int, obj: Dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        handler.wfile.write(body)

    def _send_bytes(self, handler: BaseHTTPRequestHandler, code: int, body: bytes,
                    ctype: str, extra_headers: Optional[Dict[str, str]] = None) -> None:
        handler.send_response(code)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            handler.send_header(k, v)
        handler.end_headers()
        handler.wfile.write(body)

    def _read_json(self, handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
        length = int(handler.headers.get("Content-Length") or 0)
        raw = handler.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            data = json.loads(raw or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        path = parsed.path
        if path.startswith("/api/"):
            if not self._check_token(handler):
                self._send_json(handler, 401, {"error": "unauthorized"})
                return
            if path == "/api/status":
                self._send_json(handler, 200, self.status_payload())
                return
            if path == "/api/events":
                self._handle_sse(handler)
                return
            if path == "/api/logs":
                q = parse_qs(parsed.query)
                try:
                    lines = max(1, min(500, int(q.get("lines", ["200"])[0] or 200)))
                except ValueError:
                    lines = 200
                self._send_json(
                    handler, 200,
                    {"lines": self._read_log_tail(lines), "offset": self._log_offset()},
                )
                return
            if path == "/api/logs/stream":
                q = parse_qs(parsed.query)
                try:
                    offset = max(0, int(q.get("offset", ["0"])[0] or 0))
                except ValueError:
                    offset = 0
                self._handle_log_sse(handler, offset)
                return
            if path == "/api/history":
                q = parse_qs(parsed.query).get("q", [""])[0].strip()
                msgs = (self.pet.chat_history.search(q)
                        if q else self.pet.chat_history.history)
                self._send_json(handler, 200, {"messages": msgs[-1000:]})
                return
            if path == "/api/history/export":
                ts = time.strftime("%Y%m%d_%H%M%S")
                fname = f"chat_history_{ts}.txt"
                self._send_bytes(
                    handler, 200, self._export_text().encode("utf-8"),
                    "text/plain; charset=utf-8",
                    {"Content-Disposition": f'attachment; filename="{fname}"'},
                )
                return
            if path == "/api/settings":
                self._send_json(handler, 200, self._settings_payload())
                return
            if path == "/api/games":
                self._send_json(handler, 200, self._games_payload())
                return
            if path == "/api/skills":
                self._send_json(handler, 200, self._skills_payload())
                return
            if path == "/api/memory":
                self._send_json(handler, 200, self._facts_payload())
                return
            if path.startswith("/api/skills/"):
                name = unquote(path[len("/api/skills/"):])
                detail = self._skill_detail(name)
                if detail is None:
                    self._send_json(handler, 404, {"error": "skill not found"})
                    return
                self._send_json(handler, 200, detail)
                return
            self._send_json(handler, 404, {"error": "not found"})
            return
        self._serve_static(handler, path)

    def _handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if not self._check_token(handler):
            self._send_json(handler, 401, {"error": "unauthorized"})
            return
        data = self._read_json(handler)
        p = self.pet

        if path == "/api/pet/feed":
            try:
                status = getattr(p, "status", None)
                if status is None or not hasattr(status, "feed"):
                    self._send_json(handler, 500, {"error": "pet status unavailable"})
                    return
                status.feed()
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            self._send_json(handler, 200, self.status_payload())
            return

        if path == "/api/chat":
            text = str(data.get("text") or "").strip()
            if not text:
                self._send_json(handler, 400, {"error": "empty message"})
                return
            try:
                reply = self._chat_reply(text)
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            self._send_json(handler, 200, {"reply": reply})
            return

        if path == "/api/settings/api":
            provider = str(data.get("provider") or "")
            model = str(data.get("model") or "")
            key = str(data.get("apiKey") or "").strip()
            if not key:
                key = load_api_settings()["api_key"]
            if len(key) < 10:
                self._send_json(handler, 400, {"error": "API Key 太短"})
                return
            save_api_settings(provider, model, key)
            if hasattr(p, "ai") and p.ai is not None:
                p.ai.switch(provider, model, key)
            self._send_json(handler, 200, {"ok": True})
            return

        if path == "/api/settings/api/test":
            provider = str(data.get("provider") or "")
            model = str(data.get("model") or "")
            key = str(data.get("apiKey") or "").strip()
            if not key:
                key = load_api_settings()["api_key"]
            if len(key) < 10:
                self._send_json(handler, 400, {"error": "API Key 太短"})
                return
            ok, msg = test_connection(provider, key, model)
            self._send_json(handler, 200, {"ok": ok, "message": msg})
            return

        if path == "/api/settings/system":
            try:
                self._apply_system(data)
            except ValueError as e:
                self._send_json(handler, 400, {"error": str(e)})
                return
            self._send_json(handler, 200, {"ok": True})
            return

        if path == "/api/pet/size":
            try:
                scale = float(data.get("scale", 1.0))
                scale = max(getattr(p, "min_scale", cfg.MIN_SCALE),
                            min(getattr(p, "max_scale", cfg.MAX_SCALE), scale))
                if hasattr(p, "_resize_pet"):
                    p._resize_pet(scale)
                setattr(cfg, "PET_SCALE", scale)
                cfg._save()  # 落盘，否则重启后回到 100%
            except Exception as e:
                self._send_json(handler, 500, {"error": str(e)})
                return
            actual = float(getattr(p, "scale_factor", scale))
            self._send_json(handler, 200, {"ok": True, "scale": actual})
            return

        if path == "/api/settings/font":
            try:
                size = int(data.get("size", cfg.FONT_SIZE))
            except (TypeError, ValueError):
                self._send_json(handler, 400, {"error": "字号必须是整数"})
                return
            family = str(data.get("family") or cfg.FONT_FAMILY)
            size = max(cfg.FONT_SIZE_MIN, min(cfg.FONT_SIZE_MAX, size))
            setattr(cfg, "FONT_FAMILY", family)
            setattr(cfg, "FONT_SIZE", size)
            cfg._save()  # 落盘，否则重启后字号/字体丢失
            self._send_json(handler, 200, {"ok": True, "family": family, "size": size})
            return

        if path == "/api/settings/autostart":
            want = bool(data.get("enabled"))
            try:
                from core.autostart import set_enabled

                ok, message = set_enabled(want)
            except Exception as e:
                self._send_json(handler, 200, {"ok": False, "message": str(e)})
                return
            self._send_json(handler, 200, {
                "ok": ok, "message": message, "enabled": _autostart_enabled(),
            })
            return

        if path == "/api/pet/restart":
            self._send_json(handler, 200, {"ok": True})
            root = getattr(p, "root", None)
            if root is not None and hasattr(p, "restart"):
                root.after(300, p.restart)
            return

        if path == "/api/pet/quit":
            self._send_json(handler, 200, {"ok": True})
            root = getattr(p, "root", None)
            if root is not None and hasattr(p, "quit"):
                root.after(300, p.quit)
            return

        if path.startswith("/api/games/"):
            rest = path[len("/api/games/"):]
            gm = getattr(p, "game_manager", None)
            root = getattr(p, "root", None)

            if rest.endswith("/toggle"):
                key = unquote(rest[: -len("/toggle")])
                enabled = bool(data.get("enabled"))
                if gm is not None and hasattr(gm, "set_enabled"):
                    gm.set_enabled(key, enabled)  # 纯配置写入，无 Tk 调用
                self._send_json(handler, 200, self._games_payload())
                return

            if rest.endswith("/start"):
                key = unquote(rest[: -len("/start")])
                # 启停必须回到 Tk 主线程：GameManager 会创建 Toplevel/after，
                # 从 HTTP 工作线程直接调用会跨线程操作 Tk
                if gm is not None and root is not None:
                    root.after(50, lambda k=key: gm.start(k))
                self._send_json(handler, 200, self._games_payload(active_key=key))
                return

            if rest == "stop" or rest.endswith("/stop"):
                if gm is not None and root is not None:
                    root.after(50, gm.stop)
                self._send_json(handler, 200, self._games_payload(clear_active=True))
                return

        if path == "/api/memory":
            mf = getattr(p, "memory_facts", None)
            if mf is None:
                self._send_json(handler, 200, {"ok": False, "message": "长期记忆不可用"})
                return
            if "enabled" in data:
                mf.set_enabled(bool(data.get("enabled")))
            text = str(data.get("text") or "").strip()
            added = None
            if text:
                added = mf.add(text, source="manual")
            self._send_json(handler, 200, {
                "ok": True,
                "added": added is not None,
                "memory": self._facts_payload(),
            })
            return

        if path == "/api/skills/import":
            filename = str(data.get("filename") or "")
            b64 = str(data.get("content") or "")
            if not filename or not b64:
                self._send_json(handler, 400, {"error": "缺少文件"})
                return
            is_zip = filename.lower().endswith(".zip")
            try:
                raw = base64.b64decode(b64)
            except Exception:
                self._send_json(handler, 400, {"error": "base64 解码失败"})
                return
            tmp = os.path.join(tempfile.gettempdir(), "skill_import_" + secrets.token_hex(6) + (".zip" if is_zip else ".py"))
            try:
                with open(tmp, "wb") as f:
                    f.write(raw)
                if hasattr(p, "skill_manager"):
                    if is_zip:
                        ok, msg = p.skill_manager.add_skill_zip(tmp)
                    else:
                        ok, msg = p.skill_manager.add_skill(tmp)
                else:
                    ok, msg = False, "技能管理器不可用"
            except Exception as e:
                ok, msg = False, str(e)
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            self._send_json(handler, 200, {"ok": ok, "message": msg})
            return

        if path.startswith("/api/skills/"):
            rest = path[len("/api/skills/"):]
            if rest.endswith("/toggle"):
                name = unquote(rest[: -len("/toggle")])
                enabled = bool(data.get("enabled"))
                if hasattr(p, "skill_manager") and hasattr(p.skill_manager, "toggle"):
                    p.skill_manager.toggle(name, enabled)
                self._send_json(handler, 200, {"ok": True})
                return
            if rest.endswith("/execute"):
                name = unquote(rest[: -len("/execute")])
                args = data.get("arguments") or {}
                if hasattr(p, "skill_manager") and hasattr(p.skill_manager, "execute"):
                    result = p.skill_manager.execute(name, json.dumps(args, ensure_ascii=False))
                else:
                    result = "技能管理器不可用"
                self._send_json(handler, 200, {"result": result})
                return
        self._send_json(handler, 404, {"error": "not found"})

    def _handle_delete(self, handler: BaseHTTPRequestHandler) -> None:
        path = urlparse(handler.path).path
        if not self._check_token(handler):
            self._send_json(handler, 401, {"error": "unauthorized"})
            return
        if path == "/api/history":
            if hasattr(self.pet, "chat_history"):
                self.pet.chat_history.clear()
            self._send_json(handler, 200, {"ok": True})
            return
        if path == "/api/memory":
            mf = getattr(self.pet, "memory_facts", None)
            if mf is None:
                self._send_json(handler, 200, {"ok": False})
                return
            self._send_json(handler, 200, {"ok": True, "cleared": mf.clear()})
            return
        if path.startswith("/api/memory/"):
            fact_id = unquote(path[len("/api/memory/"):])
            mf = getattr(self.pet, "memory_facts", None)
            ok = bool(mf is not None and mf.remove(fact_id))
            self._send_json(handler, 200, {"ok": ok})
            return
        if path.startswith("/api/skills/"):
            name = unquote(path[len("/api/skills/"):])
            ok = False
            if hasattr(self.pet, "skill_manager") and hasattr(self.pet.skill_manager, "remove_skill"):
                ok = bool(self.pet.skill_manager.remove_skill(name))
            self._send_json(handler, 200, {"ok": ok})
            return
        self._send_json(handler, 404, {"error": "not found"})

    # ---------- ????????????? ----------
    LOG_FILE = "kurumi.log"
    _LOG_POLL = 0.4

    def _log_file_path(self) -> str:
        return os.path.join(get_log_dir(), self.LOG_FILE)

    def _log_offset(self) -> int:
        try:
            return os.path.getsize(self._log_file_path())
        except OSError:
            return 0

    def _read_log_tail(self, lines: int = 200) -> List[str]:
        path = self._log_file_path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return []
                chunk = 4096
                pos = size
                buf = b""
                while pos > 0 and buf.count(b"\n") < lines:
                    read_start = max(0, pos - chunk)
                    f.seek(read_start)
                    buf = f.read(pos - read_start) + buf
                    pos = read_start
                text = buf.decode("utf-8", errors="replace")
                return text.splitlines()[-lines:]
        except OSError:
            return []

    def _read_log_new(self, offset: int) -> "tuple[List[str], int]":
        path = self._log_file_path()
        if not os.path.exists(path):
            return [], 0
        try:
            size = os.path.getsize(path)
            if size < offset:
                # ??????????????????
                with open(path, "rb") as f:
                    data = f.read()
                lines = data.decode("utf-8", errors="replace").splitlines()
                return ["[???????????????]"] + lines, size
            if size == offset:
                return [], offset
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read(size - offset)
            lines = data.decode("utf-8", errors="replace").splitlines()
            return lines, size
        except OSError:
            return [], offset

    def _handle_log_sse(self, handler: BaseHTTPRequestHandler, offset: int) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        try:
            while True:
                lines, offset = self._read_log_new(offset)
                if lines:
                    data = json.dumps({"lines": lines, "offset": offset}, ensure_ascii=False)
                    handler.wfile.write(f"event: log\ndata: {data}\n\n".encode("utf-8"))
                else:
                    handler.wfile.write(b": ping\n\n")
                handler.wfile.flush()
                time.sleep(self._LOG_POLL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _handle_sse(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        try:
            while True:
                data = json.dumps(self.status_payload(), ensure_ascii=False)
                handler.wfile.write(f"event: status\ndata: {data}\n\n".encode("utf-8"))
                handler.wfile.flush()
                time.sleep(self.poll_interval)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        # 不主动关闭 wfile：客户端断开后的 flush 异常由 handle_one_request 静默处理

    def _serve_static(self, handler: BaseHTTPRequestHandler, path: str) -> None:
        base = os.path.normpath(self.static_dir)
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(base, rel))
        if not (full == base or full.startswith(base + os.sep)):
            handler.send_error(403)
            return
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            self._send_json(
                handler, 503,
                {"error": "web dist not built", "hint": "run: cd web && npm run build"},
            )
            return
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError:
            self._send_json(handler, 500, {"error": "read failed"})
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        handler.send_response(200)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        handler.wfile.write(body)
