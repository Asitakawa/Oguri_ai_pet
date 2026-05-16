import json
import os
import time
import threading


class ChatHistoryManager:
    """聊天历史记录管理器"""

    def __init__(self, file_path="chat_history.json", max_length=2000):
        self.file_path = file_path
        self.max_length = max_length
        self.history = []
        self.stats = {"total_messages": 0, "last_updated": None}
        self._save_lock = threading.Lock()
        self._save_pending = False
        self.load()

    def load(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    if isinstance(raw_data, list):
                        self.history = [
                            msg for msg in raw_data
                            if isinstance(msg, dict)
                            and all(k in msg for k in ["role", "content", "timestamp"])
                        ][-self.max_length:]
                        self.stats["total_messages"] = len(self.history)
                        self.stats["last_updated"] = (
                            self.history[-1]["timestamp"] if self.history else None
                        )
        except Exception as e:
            print(f"加载聊天历史失败: {e}")
            self.history = []

    def save(self):
        """防抖保存：合并短时间内多次 save 调用为一次写入"""
        if self._save_pending:
            return
        self._save_pending = True

        def async_save():
            try:
                with self._save_lock:
                    self.history = self.history[-self.max_length:]
                    self.stats["total_messages"] = len(self.history)
                    self.stats["last_updated"] = (
                        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                        if self.history else None
                    )
                    snapshot = list(self.history)
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"保存聊天历史失败: {e}")
            finally:
                self._save_pending = False

        threading.Thread(target=async_save, daemon=True).start()

    def add(self, role, content):
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        })
        self.save()

    def get_context(self, size=100):
        return self.history[-size:]

    def clear(self):
        self.history = []
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        self.stats["total_messages"] = 0
        self.stats["last_updated"] = None

    def search(self, keyword):
        keyword = keyword.lower()
        return [
            msg for msg in self.history
            if keyword in msg["content"].lower()
            or keyword in msg["timestamp"].lower()
        ]

    def __len__(self):
        return len(self.history)
