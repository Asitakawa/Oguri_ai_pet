"""截屏时机决策与前台窗口识别

这一层决定「什么时候会截屏上传」，属于隐私边界，必须有测试锁住行为。
策略层不碰 Tk、不发网络请求，全部可注入时间与窗口快照。
"""
from __future__ import annotations

import pytest

from core import screenshot_policy as sp
from core.screenshot_policy import ScreenshotPolicy
from core.window_tracker import ForegroundWindow, describe_activity, is_idle_or_locked


def win(process="Code", title="main.py", pid=100, at=0.0):
    return ForegroundWindow(pid, process, title, at)


@pytest.fixture
def policy(monkeypatch):
    """默认：有人在场、非深夜、窗口稳定。"""
    p = ScreenshotPolicy()
    monkeypatch.setattr(sp, "idle_seconds", lambda: 0.0)
    # 2026-01-01 15:00 本地时间（非深夜）
    noonish = 1767222000.0
    monkeypatch.setattr(sp.time, "localtime", lambda _t: _FakeTime(15))
    return p, monkeypatch, noonish


class _FakeTime:
    def __init__(self, hour):
        self.tm_hour = hour


def _set_window(p, monkeypatch, w):
    monkeypatch.setattr(sp, "_safe_foreground", lambda: w)


# ── 隐私边界：不该截的时候一定不截 ────────
def test_no_screenshot_when_user_is_away(policy):
    p, monkeypatch, now = policy
    monkeypatch.setattr(sp, "idle_seconds", lambda: 9999)
    _set_window(p, monkeypatch, win())
    assert p.decide(now) is None


def test_no_screenshot_when_screen_locked(policy):
    p, monkeypatch, now = policy
    _set_window(p, monkeypatch, win("LockApp", "锁屏"))
    assert p.decide(now) is None


def test_throttled_within_min_gap(policy):
    p, monkeypatch, now = policy
    _set_window(p, monkeypatch, win())
    p.force(now)
    assert p.decide(now + sp.MIN_GAP_SECONDS - 1) is None


def test_window_change_does_not_immediately_trigger(policy):
    """刚切换窗口先观察，不要立刻截屏。"""
    p, monkeypatch, now = policy
    _set_window(p, monkeypatch, win("Code", "a.py"))
    assert p.decide(now) is None  # 第一次只是记录
    monkeypatch.setattr(sp.time, "localtime", lambda _t: _FakeTime(15))
    _set_window(p, monkeypatch, win("chrome", "百度", pid=200))
    assert p.decide(now + sp.MIN_GAP_SECONDS + 1) is None


# ── 该截的时候要能截 ──────────────────────
def test_long_same_activity_triggers(policy):
    p, monkeypatch, now = policy
    w = win("Code", "main.py")
    _set_window(p, monkeypatch, w)
    p.decide(now)  # 建立窗口基线
    later = now + sp.MIN_GAP_SECONDS + 1
    assert p.decide(later) is None, "还没待够久"
    long_enough = now + sp.SAME_WINDOW_LONG_SECONDS + sp.MIN_GAP_SECONDS + 2
    reason = p.decide(long_enough)
    assert reason is not None
    assert "写代码" in reason or "分钟" in reason


def test_late_night_triggers(policy):
    p, monkeypatch, now = policy
    monkeypatch.setattr(sp.time, "localtime", lambda _t: _FakeTime(3))
    _set_window(p, monkeypatch, win())
    p.decide(now)                       # 建立基线
    reason = p.decide(now + sp.MIN_GAP_SECONDS + 1)
    assert reason == "已经深夜了"


def test_after_idle_return_resets_dwell(policy):
    """离开一段时间回来后，不应立刻因为「同一窗口待很久」而触发。"""
    p, monkeypatch, now = policy
    _set_window(p, monkeypatch, win())
    p.decide(now)
    # 变成长时间空闲
    monkeypatch.setattr(sp, "idle_seconds", lambda: sp.IDLE_SKIP_SECONDS + 10)
    assert p.decide(now + 10) is None
    # 回来了
    monkeypatch.setattr(sp, "idle_seconds", lambda: 0.0)
    assert p.decide(now + 20) is None, "刚回来不该触发"
    assert p.decide(now + 21 + sp.SAME_WINDOW_LONG_SECONDS) is not None


def test_force_updates_throttle(policy):
    p, monkeypatch, now = policy
    _set_window(p, monkeypatch, win())
    p.force(now)
    assert p.last_shot_at == now
    assert p.decide(now + 1) is None


def test_no_repeat_trigger_within_gap_after_long_activity(policy):
    p, monkeypatch, now = policy
    _set_window(p, monkeypatch, win())
    p.decide(now)
    t = now + sp.SAME_WINDOW_LONG_SECONDS + sp.MIN_GAP_SECONDS + 2
    assert p.decide(t) is not None
    assert p.decide(t + 1) is None, "触发后应立即进入节流"


def test_snapshot_shape(policy):
    p, _monkeypatch, _now = policy
    snap = p.snapshot()
    assert {"last_shot_at", "window_since", "was_idle"} <= set(snap)


# ── 活动识别 ──────────────────────────────
@pytest.mark.parametrize("process,expect", [
    ("Code", "写代码"),
    ("pycharm64", "写代码"),
    ("WindowsTerminal", "敲命令"),
    ("chrome", "上网"),
    ("Weixin", "聊天"),
    ("WeChat", "聊天"),
    ("EXCEL", "做表格"),
    ("msedge", "上网"),
    ("unknown_app", "忙别的"),
])
def test_describe_activity(process, expect):
    assert describe_activity(win(process)) == expect


def test_describe_activity_none():
    assert describe_activity(None) == ""


def test_idle_or_locked_only_for_lock_processes():
    assert is_idle_or_locked(win("LockApp", "锁屏")) is True
    assert is_idle_or_locked(win("logonui", "")) is True
    assert is_idle_or_locked(win("Code", "main.py")) is False
    assert is_idle_or_locked(None) is False


def test_foreground_snapshot_equality():
    a = win("Code", "main.py", pid=1)
    b = win("Code", "main.py", pid=1)
    c = win("Code", "other.py", pid=1)
    d = win("chrome", "main.py", pid=2)
    assert a.same_as(b)
    assert not a.same_as(c)
    assert not a.same_as(d)
    assert not a.same_as(None)


# ── 真实 API（可能不可用，只验证不抛异常） ──
def test_get_foreground_is_safe():
    from core.window_tracker import get_foreground

    result = get_foreground()
    assert result is None or hasattr(result, "process")


def test_idle_seconds_is_non_negative():
    from core.window_tracker import idle_seconds

    assert idle_seconds() >= 0.0
