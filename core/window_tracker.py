"""前台窗口追踪 — 让桌宠"知道你在干什么"

只用 Win32 只读 API（`GetForegroundWindow` / `GetWindowTextW` /
`GetWindowThreadProcessId`），不注入、不挂钩子、不读窗口内容。
只拿到「进程名 + 窗口标题」，用来做情境判断。

用途：
- 事件触发截屏：窗口切换、长时间没换窗口、深夜等情境才看一眼，
  取代原来「每 N 秒无条件截屏」的定时器（既省 token 又更像真的在看）
- 情境台词：长时间同一窗口 → 提醒休息

拿不到信息时（非 Windows、权限受限）全部降级为 None，调用方需容忍。
"""
from __future__ import annotations

import ctypes
import os
import time
from typing import Optional

from utils.logger import get_logger

log = get_logger("window_tracker")

_HAS_WIN32 = os.name == "nt"


class ForegroundWindow:
    """一帧前台窗口快照。"""

    __slots__ = ("pid", "process", "title", "at")

    def __init__(self, pid: int, process: str, title: str, at: float) -> None:
        self.pid = pid
        self.process = process
        self.title = title
        self.at = at

    def __repr__(self) -> str:
        return f"ForegroundWindow({self.process!r}, {self.title!r})"

    def same_as(self, other: Optional["ForegroundWindow"]) -> bool:
        if other is None:
            return False
        return self.pid == other.pid and self.title == other.title


def _process_name(pid: int) -> str:
    """进程名（不带 .exe）。失败返回空串。"""
    try:
        import psutil  # type: ignore

        return psutil.Process(pid).name().removesuffix(".exe")
    except Exception:
        return ""


def get_foreground() -> Optional[ForegroundWindow]:
    """读取当前前台窗口；不可用时返回 None。"""
    if not _HAS_WIN32:
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        pid_val = int(pid.value)
        return ForegroundWindow(pid_val, _process_name(pid_val), title, time.time())
    except Exception:
        log.debug("读取前台窗口失败", exc_info=True)
        return None


# 常见进程名 → 人类可读的活动类型。命中不了就当普通工作。
_ACTIVITY_HINTS = (
    ("code", "写代码"), ("pycharm", "写代码"), ("idea64", "写代码"),
    ("devenv", "写代码"), ("sublime_text", "写代码"), ("notepad++", "写代码"),
    ("vim", "写代码"), ("goland64", "写代码"), ("webstorm64", "写代码"),
    ("windowsterminal", "敲命令"), ("powershell", "敲命令"), ("cmd", "敲命令"),
    ("wt", "敲命令"), ("bash", "敲命令"),
    ("chrome", "上网"), ("msedge", "上网"), ("firefox", "上网"),
    ("brave", "上网"), ("opera", "上网"),
    ("explorer", "翻文件"),
    ("wechat", "聊天"), ("weixin", "聊天"), ("qq", "聊天"),
    ("telegram", "聊天"), ("discord", "聊天"),
    ("slack", "聊天"), ("dingtalk", "聊天"), ("feishu", "聊天"), ("lark", "聊天"),
    ("excel", "做表格"), ("winword", "写文档"), ("powerpnt", "做演示"),
    ("wps", "做文档"), ("et", "做表格"), ("wpp", "做演示"),
    ("obs64", "录屏"), ("obs", "录屏"),
    ("photoshop", "修图"), ("illustrator", "画图"), ("figma", "画图"),
    ("steam", "玩游戏"), ("steamwebhelper", "玩游戏"),
    ("spotify", "听歌"), ("cloudmusic", "听歌"), ("qqmusic", "听歌"),
    ("potplayer", "看视频"), ("vlc", "看视频"), ("mpc-hc64", "看视频"),
    ("bilibili", "看视频"), ("youku", "看视频"),
    ("mstsc", "远程桌面"), ("teamviewer", "远程桌面"),
    ("idle", ""), ("lockapp", ""), ("logonui", ""),
)


def describe_activity(win: Optional[ForegroundWindow]) -> str:
    """把前台窗口翻译成一句人话的活动描述。"""
    if win is None:
        return ""
    name = (win.process or "").lower()
    for key, label in _ACTIVITY_HINTS:
        if key in name:
            return label
    return "忙别的"


def is_idle_or_locked(win: Optional[ForegroundWindow]) -> bool:
    """锁屏 / 无人操作。"""
    if win is None:
        return False
    return describe_activity(win) == "" and bool(win.process)


def idle_seconds() -> float:
    """系统级空闲时长（秒）。取不到时返回 0。"""
    if not _HAS_WIN32:
        return 0.0
    try:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, millis / 1000.0)
    except Exception:
        return 0.0
