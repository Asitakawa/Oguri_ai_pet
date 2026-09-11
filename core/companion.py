"""陪伴统计 — 跨会话累积的相处记录

落在数据目录的 `companion.json`。所有写入都是「读-改-写 + 原子替换」，
避免桌宠被强杀时把文件写坏。
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time

from core.paths import get_data_path
from utils.logger import get_logger

log = get_logger("companion")

FILE_NAME = "companion.json"

_DEFAULTS = {
    "first_seen": 0.0,       # 首次启动时间戳
    "last_seen": 0.0,        # 上次退出/心跳时间戳
    "total_seconds": 0.0,    # 累计陪伴时长（秒）
    "sessions": 0,           # 启动次数
    "feed_count": 0,         # 累计喂饭团次数
    "chat_rounds": 0,        # 累计聊天轮数（一问一答算一轮）
    "drag_count": 0,         # 累计拖拽次数
    "max_fly_meters": 0.0,   # 一飞冲天最高纪录
    "games_played": 0,       # 累计开局次数
    "facts_learned": 0,      # 累计沉淀的长期记忆条数
    "onboarded": 0,          # 是否已经给过首次运行提示（0/1）
}


def _atomic_write(path: str, data: dict) -> None:
    """先写临时文件再替换，避免中途崩溃留下半截 JSON。"""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


class CompanionStats:
    """线程安全的陪伴统计。"""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or get_data_path(FILE_NAME)
        self._lock = threading.Lock()
        self._data = dict(_DEFAULTS)
        self._session_start = time.time()
        self._load()

    # ── 读写 ──────────────────────────────
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for k, default in _DEFAULTS.items():
                    v = raw.get(k, default)
                    # 类型不对就用默认值，避免手改文件后处处崩
                    self._data[k] = type(default)(v) if isinstance(v, (int, float)) else default
        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning("陪伴统计读取失败，使用默认值: %s", e)

    def _save_locked(self) -> None:
        try:
            _atomic_write(self._path, self._data)
        except OSError as e:
            log.warning("陪伴统计保存失败: %s", e)

    def save(self) -> None:
        with self._lock:
            self._accumulate_locked()
            self._save_locked()

    def _accumulate_locked(self) -> None:
        now = time.time()
        if not self._data["first_seen"]:
            self._data["first_seen"] = now
        self._data["last_seen"] = now
        # total_seconds 按会话增量累加，而不是用 now - first_seen，
        # 否则「陪伴时长」会把关机的日子也算进去
        self._data["total_seconds"] = (
            self._data.get("total_seconds", 0.0) + max(0.0, now - self._session_start)
        )
        self._session_start = now

    # ── 生命周期 ──────────────────────────
    def start_session(self) -> float:
        """记录一次启动，返回距上次离开的秒数（首次启动返回 -1）。"""
        with self._lock:
            last = self._data.get("last_seen", 0.0)
            away = (time.time() - last) if last else -1.0
            self._data["sessions"] = self._data.get("sessions", 0) + 1
            self._data["first_seen"] = self._data.get("first_seen") or time.time()
            self._save_locked()
            return away

    # ── 计数 ──────────────────────────────
    def bump(self, key: str, delta: int = 1) -> None:
        if key not in _DEFAULTS:
            return
        with self._lock:
            self._data[key] = self._data.get(key, 0) + delta
            self._save_locked()

    def set_flag(self, key: str, value: int = 1) -> None:
        """一次性标记（如「已经引导过」）。"""
        if key not in _DEFAULTS:
            return
        with self._lock:
            self._data[key] = value
            self._save_locked()

    def record_max(self, key: str, value: float) -> bool:
        """只在刷新纪录时写入，返回是否破纪录。"""
        if key not in _DEFAULTS:
            return False
        return self.set_max(key, value)

    def set_max(self, key: str, value: float) -> bool:
        with self._lock:
            if value > self._data.get(key, 0):
                self._data[key] = value
                self._save_locked()
                return True
            return False

    # ── 读取 ──────────────────────────────
    def snapshot(self) -> dict:
        with self._lock:
            d = dict(self._data)
            # 附上本次会话的实时时长，让面板不必等退出才更新
            d["current_session_seconds"] = max(0.0, time.time() - self._session_start)
            return d

    def days_together(self) -> int:
        with self._lock:
            first = self._data.get("first_seen", 0.0)
        if not first:
            return 0
        return max(1, int((time.time() - first) // 86400) + 1)

    def away_text(self, away_seconds: float) -> str:
        """按离开时长给出重逢台词；无话可说时返回空串。"""
        if away_seconds < 0:
            return ""
        hours = away_seconds / 3600.0
        if hours < 1:
            return ""
        if hours < 6:
            return "训练员回来啦，小栗帽一直在的"
        if hours < 24:
            return "唔…训练员刚才去哪儿了，小栗帽等了好久"
        days = int(hours // 24)
        if days < 7:
            return f"{days}天没见了…训练员有好好吃饭吗"
        if days < 30:
            return f"{days}天…小栗帽差点以为训练员不来了"
        return "好久好久不见，训练员。小栗帽还记得你的味道"
