"""聊天记忆：持久化 / 截断 / 搜索 / 清空 / 防抖写盘"""
import json
import time

from core.chat_history import ChatHistoryManager


def test_add_and_reload(tmp_path):
    path = str(tmp_path / "chat.json")
    m = ChatHistoryManager(path)
    m.add("user", "你好")
    m.add("assistant", "你好呀")
    m.save(sync=True)
    m2 = ChatHistoryManager(path)
    assert len(m2) == 2
    assert m2.history[0]["content"] == "你好"
    assert m2.stats["total_messages"] == 2


def test_truncate_on_load(tmp_path):
    path = str(tmp_path / "chat.json")
    m = ChatHistoryManager(path, max_length=2)
    m.add("user", "1")
    m.add("user", "2")
    m.add("user", "3")
    m.save(sync=True)
    m2 = ChatHistoryManager(path, max_length=2)
    assert len(m2) == 2
    assert m2.history[-1]["content"] == "3"


def test_search(tmp_path):
    m = ChatHistoryManager(str(tmp_path / "chat.json"))
    m.add("user", "今天吃拉面")
    assert len(m.search("拉面")) == 1
    assert len(m.search("不存在")) == 0


def test_clear(tmp_path):
    path = str(tmp_path / "chat.json")
    m = ChatHistoryManager(path)
    m.add("user", "x")
    m.save(sync=True)
    m.clear()
    assert len(m) == 0
    assert not tmp_path.joinpath("chat.json").exists()


def test_debounced_write(tmp_path, monkeypatch):
    monkeypatch.setattr("core.chat_history._DEBOUNCE_SECONDS", 0.2)
    path = str(tmp_path / "chat.json")
    m = ChatHistoryManager(path)
    m.add("user", "a")
    m.add("assistant", "b")  # 两次 add 应合并为一次写盘
    time.sleep(0.5)
    data = json.loads(tmp_path.joinpath("chat.json").read_text(encoding="utf-8"))
    assert len(data) == 2
