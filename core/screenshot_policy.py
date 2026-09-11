"""截屏时机决策 — 用情境触发取代固定定时器

原实现是 `_api_talk_loop` 里「每 60–300 秒无条件截屏一次」，问题：
- 和你在做什么无关，你不在电脑前它也照样截屏上传
- 与桌宠「注意到训练员在忙什么」的设定脱节

这里改成纯决策层（不碰 Tk、不发请求，便于单测）：
输入「前台窗口变化 + 空闲时长 + 距上次截屏多久」，输出该不该看一眼 + 理由。
真正截屏与调用 AI 由调用方执行。
"""
from __future__ import annotations

import time
from typing import Optional

from core.window_tracker import (
    ForegroundWindow,
    describe_activity,
    idle_seconds,
    is_idle_or_locked,
)

# 触发阈值
MIN_GAP_SECONDS = 90          # 两次 AI 搭话的最短间隔（防刷屏）
SAME_WINDOW_LONG_SECONDS = 50 * 60   # 同一个窗口连续待这么久 → 关心一下
IDLE_SKIP_SECONDS = 300       # 人不在（系统空闲）就别打扰
AWAY_RESET_SECONDS = 600      # 空闲超过这么久，回来后重置「同一窗口」计时
LATE_NIGHT_HOURS = (0, 1, 2, 3, 4, 5)  # 深夜时段


class ScreenshotPolicy:
    """有状态的情境决策器。"""

    def __init__(self) -> None:
        self._last_shot_at = 0.0
        self._last_window: Optional[ForegroundWindow] = None
        self._window_since = 0.0
        self._was_idle = False

    # ── 对外 ──────────────────────────────
    def decide(self, now: Optional[float] = None) -> Optional[str]:
        """返回触发理由；None 表示这次不该截屏。"""
        now = time.time() if now is None else now
        win = _safe_foreground()

        # 人不在：不截屏，也不上传
        idle = idle_seconds()
        if idle >= IDLE_SKIP_SECONDS or is_idle_or_locked(win):
            self._was_idle = True
            return None
        if self._was_idle:
            # 刚回来：重置窗口计时，别立刻因为"同一窗口待了很久"触发
            self._was_idle = False
            self._window_since = now
            self._last_window = win

        if now - self._last_shot_at < MIN_GAP_SECONDS:
            return None

        # 记录窗口驻留时长
        if not win.same_as(self._last_window):
            self._last_window = win
            self._window_since = now
            return None  # 刚切换窗口，先观察一下再决定

        dwell = now - self._window_since
        hour = time.localtime(now).tm_hour

        if dwell >= SAME_WINDOW_LONG_SECONDS:
            activity = describe_activity(win) or "做着什么"
            self._touch(now)
            return f"同一件事连续 {activity} 快 {int(dwell // 60)} 分钟了"

        if hour in LATE_NIGHT_HOURS:
            self._touch(now)
            return "已经深夜了"

        return None

    def force(self, now: Optional[float] = None) -> str:
        """手动/强制截屏时调用，仅用于更新节流时间。"""
        self._touch(time.time() if now is None else now)
        return "手动"

    def note_window_change(self, now: Optional[float] = None) -> None:
        self._window_since = time.time() if now is None else now

    # ── 内部 ──────────────────────────────
    def _touch(self, now: float) -> None:
        self._last_shot_at = now

    @property
    def last_shot_at(self) -> float:
        return self._last_shot_at

    def snapshot(self) -> dict:
        return {
            "last_shot_at": self._last_shot_at,
            "window_since": self._window_since,
            "was_idle": self._was_idle,
        }


def _safe_foreground() -> Optional[ForegroundWindow]:
    try:
        from core.window_tracker import get_foreground

        return get_foreground()
    except Exception:
        return None
