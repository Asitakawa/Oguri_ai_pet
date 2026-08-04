"""聊天记忆管理 — 线程安全 + 防抖批量写盘"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, List, Optional

from utils.logger import get_logger

log = get_logger("chat_history")

_DEBOUNCE_SECONDS = 5.0


class ChatHistoryManager:
    def __init__(self, file_path: str = "chat_history.json",
                 max_length: int = 2000) -> None:
        self.file_path = file_path
        self.max_length = max_length
        self._lock = threading.Lock()
        self.history: List[dict] = []
        self.stats: Dict[str, Optional[str]] = {"total_messages": 0, "last_updated": None}
        # 防抖写盘状态
        self._dirty = False
        self._pending_snap: Optional[List[dict]] = None
        self._debounce_timer: Optional[threading.Timer] = None
        self.load()

    def load(self) -> None:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        with self._lock:
                            self.history = [
                                m for m in raw
                                if isinstance(m, dict)
                                and all(k in m for k in ("role", "content", "timestamp"))
                            ][-self.max_length:]
                            self.stats["total_messages"] = len(self.history)
                            self.stats["last_updated"] = (
                                self.history[-1]["timestamp"] if self.history else None
                            )
        except Exception:
            with self._lock:
                self.history = []

    def save(self, sync: bool = False) -> None:
        """保存快照；sync=True 立即写盘，否则防抖合并（默认 5s）。"""
        with self._lock:
            snap = list(self.history)
            self.stats["total_messages"] = len(snap)
            self.stats["last_updated"] = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) if snap else None
            )
            if sync:
                timer = self._debounce_timer
                self._debounce_timer = None
                self._dirty = False
            else:
                self._pending_snap = snap
                self._dirty = True
                if self._debounce_timer is None:
                    t = threading.Timer(_DEBOUNCE_SECONDS, self._flush_debounced)
                    t.daemon = True
                    t.start()
                    self._debounce_timer = t

        if sync:
            if timer:
                timer.cancel()
            self._write(snap)

    def _flush_debounced(self) -> None:
        with self._lock:
            self._debounce_timer = None
            if not self._dirty:
                return
            self._dirty = False
            snap = self._pending_snap
        self._write(snap)

    def _write(self, snap: Optional[List[dict]]) -> None:
        if snap is None:
            return
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("保存聊天历史失败: %s", e)

    def add(self, role: str, content: str) -> None:
        with self._lock:
            self.history.append({
                "role": role,
                "content": content,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            })
        self.save()

    def get_context(self, size: int = 100) -> List[dict]:
        with self._lock:
            return list(self.history[-size:])

    def clear(self) -> None:
        with self._lock:
            self.history = []
            self.stats["total_messages"] = 0
            self.stats["last_updated"] = None
            timer = self._debounce_timer
            self._debounce_timer = None
            self._dirty = False
            self._pending_snap = None
        if timer:
            timer.cancel()
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        except OSError as e:
            log.warning("清除历史文件失败: %s", e)
            self.save(sync=True)

    def search(self, keyword: str) -> List[dict]:
        kw = keyword.lower()
        with self._lock:
            return [
                m for m in self.history
                if kw in m["content"].lower() or kw in m["timestamp"].lower()
            ]

    def __len__(self) -> int:
        with self._lock:
            return len(self.history)
