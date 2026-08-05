# -*- coding: utf-8 -*-
"""管理面板 API 冒烟测试（假桌宠，不开 GUI）。
用法: .venv\\Scripts\\python.exe tools\\test_web_api.py
"""
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config as cfg
from core.pet_state import PetStatus
from core.chat_history import ChatHistoryManager
from core.web_server import ManagementServer

SETTINGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "settings.json")
backup = open(SETTINGS, "rb").read() if os.path.exists(SETTINGS) else None
cfg_snap = {k: getattr(cfg, k) for k in (
    "MIN_AUTO_REPLY", "MAX_AUTO_REPLY", "PRESET_MIN_INTERVAL",
    "PRESET_MAX_INTERVAL", "MEMORY_CONTEXT_SIZE", "FONT_FAMILY", "FONT_SIZE")}
CHAT = os.path.join(tempfile.gettempdir(), "test_web_api_chat.json")
if os.path.exists(CHAT):
    os.remove(CHAT)


class FakeAI:
    def ask(self, *a, **k):
        return ("测试回复", "")


class FakeSkill:
    def list_skills(self):
        return []

    def get_tools(self):
        return []

    def execute(self, *a, **k):
        return ""


class FakePet:
    def __init__(self):
        self.status = PetStatus()
        self.chat_history = ChatHistoryManager(CHAT)
        self.ai = FakeAI()
        self.skill_manager = FakeSkill()
        self.start_time = time.time()
        self.min_auto_reply_time = cfg.MIN_AUTO_REPLY
        self.max_auto_reply_time = cfg.MAX_AUTO_REPLY
        self.preset_min_interval = cfg.PRESET_MIN_INTERVAL
        self.preset_max_interval = cfg.PRESET_MAX_INTERVAL
        self.scale_factor = 1.0
        self.min_scale = 0.5
        self.max_scale = 2.0
        self.root = None
        self._resized = []

    def _resize_pet(self, scale):
        self._resized.append(scale)


def main():
    pet = FakePet()
    srv = ManagementServer(pet, static_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "dist"),
                           poll_interval=1.0)
    srv.start()
    base = srv.url().split("?")[0]
    token = srv.url().split("token=")[1]

    def call(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method)
        req.add_header("X-Management-Token", token)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    try:
        st, b = call("GET", "/api/history")
        assert st == 200 and json.loads(b)["messages"] == [], (st, b[:120])
        print("1 history empty ok")

        st, b = call("POST", "/api/chat", {"text": "你好，小栗帽"})
        assert st == 200 and json.loads(b)["reply"] == "测试回复", (st, b)
        print("2 chat reply ok")

        st, b = call("GET", "/api/history")
        msgs = json.loads(b)["messages"]
        assert len(msgs) == 2 and msgs[0]["role"] == "user" and msgs[1]["role"] == "assistant"
        assert msgs[0]["content"] == "你好，小栗帽" and msgs[1]["content"] == "测试回复"
        print("3 history 2 msgs ok (content intact)")

        st, b = call("GET", "/api/history?q=" + urllib.request.quote("你好"))
        assert len(json.loads(b)["messages"]) == 1, b
        print("4 search ok")

        st, b = call("GET", "/api/history/export")
        assert st == 200 and "你好" in b and "测试回复" in b
        print("5 export ok")

        st, b = call("GET", "/api/settings")
        s = json.loads(b)
        assert all(k in s for k in ("api", "system", "font", "pet"))
        assert len(s["api"]["providers"]) >= 4 and len(s["font"]["families"]) >= 1
        print("6 settings payload ok")

        st, b = call("POST", "/api/settings/system",
                     {"minAutoReply": 61, "maxAutoReply": 299, "presetMin": 121,
                      "presetMax": 599, "memoryRounds": 150})
        assert st == 200, (st, b)
        assert cfg.MIN_AUTO_REPLY == 61 and cfg.MEMORY_CONTEXT_SIZE == 300
        print("7 system settings ok (cfg applied)")

        st, b = call("POST", "/api/pet/size", {"scale": 1.5})
        assert st == 200 and pet._resized == [1.5], (st, b)
        print("8 pet size ok")

        st, b = call("POST", "/api/settings/font", {"family": "KaiTi", "size": 14})
        assert st == 200 and cfg.FONT_FAMILY == "KaiTi" and cfg.FONT_SIZE == 14
        print("9 font settings ok")

        st, b = call("DELETE", "/api/history")
        assert st == 200
        st, b = call("GET", "/api/history")
        assert json.loads(b)["messages"] == []
        print("10 clear history ok")

        print("ALL PHASE-3 API TESTS PASS")
    finally:
        srv.stop()


if __name__ == "__main__":
    try:
        main()
    finally:
        for k, v in cfg_snap.items():
            setattr(cfg, k, v)
        if backup is not None:
            with open(SETTINGS, "wb") as f:
                f.write(backup)
        elif os.path.exists(SETTINGS):
            os.remove(SETTINGS)
        if os.path.exists(CHAT):
            os.remove(CHAT)