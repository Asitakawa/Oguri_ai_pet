import json
import os
import time
import threading


class ChatHistoryManager:
    def __init__(self, file_path="chat_history.json", max_length=2000):
        self.file_path = file_path
        self.max_length = max_length
        self._lock = threading.Lock()
        self._save_event = threading.Event()
        self.history = []
        self.stats = {"total_messages": 0, "last_updated": None}
        self.load()

    def load(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        with self._lock:
                            self.history = [
                                m for m in raw
                                if isinstance(m, dict)
                                and all(k in m for k in ["role", "content", "timestamp"])
                            ][-self.max_length:]
                            self.stats["total_messages"] = len(self.history)
                            self.stats["last_updated"] = (
                                self.history[-1]["timestamp"] if self.history else None
                            )
        except Exception:
            with self._lock:
                self.history = []

    def save(self, sync=False):
        with self._lock:
            snap = list(self.history)
            self.stats["total_messages"] = len(snap)
            self.stats["last_updated"] = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                if snap else None
            )

        def _write():
            try:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(snap, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"保存聊天历史失败: {e}")
            finally:
                if sync:
                    self._save_event.set()

        if sync:
            self._save_event.clear()
            _write()
            return
        threading.Thread(target=_write, daemon=True).start()

    def add(self, role, content):
        with self._lock:
            self.history.append({
                "role": role,
                "content": content,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            })
        self.save()

    def get_context(self, size=100):
        with self._lock:
            return list(self.history[-size:])

    def clear(self):
        with self._lock:
            self.history = []
            self.stats["total_messages"] = 0
            self.stats["last_updated"] = None
        try:
            if os.path.exists(self.file_path):
                os.remove(self.file_path)
        except OSError as e:
            print(f"清除历史文件失败: {e}")
            self.save(sync=True)

    def search(self, keyword):
        kw = keyword.lower()
        with self._lock:
            return [
                m for m in self.history
                if kw in m["content"].lower() or kw in m["timestamp"].lower()
            ]

    def __len__(self):
        with self._lock:
            return len(self.history)
