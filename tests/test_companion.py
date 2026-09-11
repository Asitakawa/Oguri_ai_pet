"""陪伴统计与宠物状态持久化

覆盖：跨会话累积、离线衰减、原子写盘、异常文件容错。
"""
from __future__ import annotations

import json
import time

import pytest

from core import config as cfg
from core.companion import CompanionStats
from core.pet_state import PetStatus


# ── 陪伴统计 ────────────────────────────
def test_companion_defaults(tmp_path):
    c = CompanionStats(str(tmp_path / "companion.json"))
    snap = c.snapshot()
    assert snap["sessions"] == 0
    assert snap["total_seconds"] == 0.0
    assert snap["feed_count"] == 0


def test_companion_counts_persist_across_instances(tmp_path):
    path = str(tmp_path / "companion.json")
    c1 = CompanionStats(path)
    c1.bump("feed_count", 3)
    c1.bump("chat_rounds", 2)
    c2 = CompanionStats(path)
    snap = c2.snapshot()
    assert snap["feed_count"] == 3
    assert snap["chat_rounds"] == 2


def test_companion_unknown_key_ignored(tmp_path):
    c = CompanionStats(str(tmp_path / "companion.json"))
    c.bump("not_a_field", 5)
    assert "not_a_field" not in c.snapshot()


def test_companion_start_session_reports_away_time(tmp_path):
    path = str(tmp_path / "companion.json")
    c = CompanionStats(path)
    assert c.start_session() == -1.0, "首次启动没有「上次离开」时间"

    # 人为把 last_seen 挪到 3 小时前
    data = json.loads((tmp_path / "companion.json").read_text(encoding="utf-8"))
    data["last_seen"] = time.time() - 3 * 3600
    (tmp_path / "companion.json").write_text(json.dumps(data), encoding="utf-8")

    c2 = CompanionStats(path)
    away = c2.start_session()
    assert 3 * 3600 - 60 < away < 3 * 3600 + 60
    # 这是第二次启动（第一次是上面那个实例）
    assert c2.snapshot()["sessions"] == 2


def test_companion_accumulates_time_per_session(tmp_path):
    """陪伴时长应按会话增量累加，不能把关机的日子也算进去。"""
    path = str(tmp_path / "companion.json")
    c = CompanionStats(path)
    time.sleep(0.05)
    c.save()
    first = c.snapshot()["total_seconds"]
    assert first >= 0.05

    time.sleep(0.05)
    c.save()
    assert c.snapshot()["total_seconds"] > first


def test_companion_record_max(tmp_path):
    c = CompanionStats(str(tmp_path / "companion.json"))
    assert c.record_max("max_fly_meters", 120.0) is True
    assert c.record_max("max_fly_meters", 80.0) is False
    assert c.record_max("max_fly_meters", 200.0) is True
    assert c.snapshot()["max_fly_meters"] == 200.0


def test_companion_survives_corrupt_file(tmp_path):
    path = tmp_path / "companion.json"
    path.write_text("{ this is not json", encoding="utf-8")
    c = CompanionStats(str(path))
    assert c.snapshot()["sessions"] == 0
    c.bump("feed_count", 1)  # 仍应可写
    assert CompanionStats(str(path)).snapshot()["feed_count"] == 1


def test_companion_survives_wrong_types(tmp_path):
    path = tmp_path / "companion.json"
    path.write_text(json.dumps({"feed_count": "很多", "sessions": None}), encoding="utf-8")
    c = CompanionStats(str(path))
    assert isinstance(c.snapshot()["feed_count"], int)


def test_companion_days_together(tmp_path):
    path = tmp_path / "companion.json"
    c = CompanionStats(path)
    # 从未记录过 first_seen
    assert CompanionStats(str(tmp_path / "other.json")).days_together() == 0
    c.start_session()
    first = time.time()
    assert c.days_together() >= 1

    data = json.loads(path.read_text(encoding="utf-8"))
    data["first_seen"] = first - 10 * 86400
    path.write_text(json.dumps(data), encoding="utf-8")
    assert CompanionStats(path).days_together() == 11


@pytest.mark.parametrize("hours,expect_empty", [
    (0.2, True),    # 不到一小时：不啰嗦
    (6, False),     # 当天
    (30, False),    # 一天多
    (24 * 5, False),
    (24 * 60, False),
])
def test_companion_away_text_tiers(tmp_path, hours, expect_empty):
    c = CompanionStats(str(tmp_path / "companion.json"))
    text = c.away_text(hours * 3600)
    if expect_empty:
        assert text == ""
    else:
        assert text, "离开这么久应该有重逢台词"


def test_companion_away_text_first_run_is_silent(tmp_path):
    c = CompanionStats(str(tmp_path / "companion.json"))
    assert c.away_text(-1.0) == ""


def test_companion_away_text_mentions_days(tmp_path):
    c = CompanionStats(str(tmp_path / "companion.json"))
    assert "3天" in c.away_text(3 * 86400)


# ── 宠物状态持久化 ──────────────────────
def test_pet_state_starts_full_on_first_run(tmp_path):
    s = PetStatus(str(tmp_path / "pet_state.json"), autostart=False)
    assert s.hunger == cfg.HUNGER_MAX
    assert s.energy == cfg.ENERGY_MAX
    assert s.offline_minutes == 0.0


def test_pet_state_persists_across_restart(tmp_path):
    path = str(tmp_path / "pet_state.json")
    s = PetStatus(path, autostart=False)
    s.feed()  # 满值喂食不变，先手动压低
    s.hunger = 80.0
    s.energy = 40.0
    s.save()

    s2 = PetStatus(path, autostart=False)
    # 刚存完就重启，离线补偿极短，数值应基本不变
    assert 79.0 < s2.hunger <= 80.0
    assert 40.0 <= s2.energy < 41.0


def test_pet_state_offline_decay(tmp_path):
    path = tmp_path / "pet_state.json"
    path.write_text(json.dumps({
        "hunger": 100.0,
        "energy": 0.0,
        "saved_at": time.time() - 60 * 30,  # 离开 30 分钟
    }), encoding="utf-8")
    s = PetStatus(str(path), autostart=False)
    assert s.offline_minutes == pytest.approx(30, abs=0.5)
    # 饱腹 -2/分钟 → 100 - 60 = 40
    assert s.hunger == pytest.approx(40, abs=2)
    # 活力 +1/分钟 → 30
    assert s.energy == pytest.approx(30, abs=2)


def test_pet_state_offline_decay_is_capped(tmp_path):
    """离开很久也按上限截断，不会一回来就是 0。"""
    path = tmp_path / "pet_state.json"
    path.write_text(json.dumps({
        "hunger": 100.0,
        "energy": 0.0,
        "saved_at": time.time() - 60 * 60 * 24 * 30,  # 离开 30 天
    }), encoding="utf-8")
    s = PetStatus(str(path), autostart=False)
    from core.pet_state import MAX_OFFLINE_MINUTES

    assert s.offline_minutes == pytest.approx(MAX_OFFLINE_MINUTES)
    assert s.hunger == pytest.approx(
        max(0.0, 100 - cfg.HUNGER_DECAY_PER_MIN * MAX_OFFLINE_MINUTES), abs=1)


def test_pet_state_clamps_out_of_range_values(tmp_path):
    path = tmp_path / "pet_state.json"
    path.write_text(json.dumps({"hunger": 9999, "energy": -50, "saved_at": 0}),
                    encoding="utf-8")
    s = PetStatus(str(path), autostart=False)
    assert s.hunger == cfg.HUNGER_MAX
    assert s.energy == 0.0


def test_pet_state_survives_corrupt_file(tmp_path):
    path = tmp_path / "pet_state.json"
    path.write_text("not json at all", encoding="utf-8")
    s = PetStatus(str(path), autostart=False)
    assert s.hunger == cfg.HUNGER_MAX
    s.hunger = 42.0
    s.save()  # 仍应可写
    assert PetStatus(str(path), autostart=False).hunger == pytest.approx(42.0, abs=0.05)


def test_pet_state_feed_saves(tmp_path):
    path = tmp_path / "pet_state.json"
    s = PetStatus(path, autostart=False)
    s.hunger = 10.0
    s.feed()
    assert s.hunger == 10.0 + cfg.FEED_HUNGER_BOOST
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["hunger"] == pytest.approx(10.0 + cfg.FEED_HUNGER_BOOST)


def test_pet_state_stop_saves(tmp_path):
    path = tmp_path / "pet_state.json"
    s = PetStatus(path, autostart=False)
    s.hunger = 55.0
    s.stop()
    # 重载时会补算极短的离线衰减，给一点容差
    assert PetStatus(str(path), autostart=False).hunger == pytest.approx(55.0, abs=0.05)


def test_pet_state_atomic_write_leaves_no_temp(tmp_path):
    path = tmp_path / "pet_state.json"
    s = PetStatus(path, autostart=False)
    s.save()
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


# ── 计数集中在 core 层（两条调用路径都只记一次） ──
def test_feed_counted_by_status_not_ui(tmp_path):
    """喂食可能来自右键菜单或管理面板，计数必须在 PetStatus.feed 内。"""
    c = CompanionStats(str(tmp_path / "companion.json"))
    s = PetStatus(str(tmp_path / "pet_state.json"), autostart=False, companion=c)
    s.hunger = 0.0
    s.feed()
    s.feed()
    assert c.snapshot()["feed_count"] == 2


def test_feed_without_companion_is_safe(tmp_path):
    s = PetStatus(str(tmp_path / "pet_state.json"), autostart=False, companion=None)
    s.feed()  # 不应抛异常
    assert s.hunger == cfg.HUNGER_MAX


def test_chat_rounds_counted_on_assistant_reply(tmp_path):
    from core.chat_history import ChatHistoryManager

    c = CompanionStats(str(tmp_path / "companion.json"))
    m = ChatHistoryManager(str(tmp_path / "chat.json"), companion=c)
    m.add("user", "你好")
    assert c.snapshot()["chat_rounds"] == 0, "只有用户消息不算一轮"
    m.add("assistant", "你好呀")
    m.add("user", "在吗")
    m.add("assistant", "在的")
    assert c.snapshot()["chat_rounds"] == 2


def test_chat_rounds_without_companion_is_safe(tmp_path):
    from core.chat_history import ChatHistoryManager

    m = ChatHistoryManager(str(tmp_path / "chat.json"), companion=None)
    m.add("assistant", "x")  # 不应抛异常
    assert len(m) == 1


def test_games_played_counted_by_manager(tmp_path, monkeypatch):
    """开局计数必须在 GameManager.start 内：菜单与面板都会走它。"""
    import game as game_mod

    c = CompanionStats(str(tmp_path / "companion.json"))

    class FakePet:
        companion = c
        x = y = 0
        screen_w = screen_h = 1000
        pet_size = (100, 100)
        label = None
        root = None

    mgr = game_mod.GameManager(FakePet())
    monkeypatch.setattr(game_mod, "GAMES", {
        "stub": {"name": "桩游戏", "desc": "", "cls": _StubGame},
    })
    mgr.start("stub")
    mgr.start("stub")
    assert c.snapshot()["games_played"] == 2


class _StubGame:
    NAME = "桩游戏"

    def __init__(self, pet):
        self.pet = pet

    def start(self):
        pass

    def stop(self):
        pass


def test_game_manager_counts_without_companion(tmp_path, monkeypatch):
    import game as game_mod

    class FakePet:
        companion = None

    mgr = game_mod.GameManager(FakePet())
    monkeypatch.setattr(game_mod, "GAMES", {
        "stub": {"name": "桩游戏", "desc": "", "cls": _StubGame},
    })
    mgr.start("stub")  # 不应抛异常
