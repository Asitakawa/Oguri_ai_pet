# -*- coding: utf-8 -*-
"""阶段 4 API 冒烟：游戏开关/启停 + 技能列表/详情/参数/执行/导入/删除。"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.web_server import ManagementServer

GAME_NAMES = {"fly_high": "一飞冲天", "onigiri_catch": "接饭团", "eating_rush": "大胃王速吃",
              "dash_run": "冲刺障碍跑", "fishing": "钓鱼时机"}


class _Active:
    def __init__(self, name):
        self.NAME = name


class FakeGameManager:
    def __init__(self):
        self._config = {k: True for k in GAME_NAMES}
        self._active = None

    def list_all(self):
        return [(k, GAME_NAMES[k], self._config[k]) for k in GAME_NAMES]

    def set_enabled(self, key, enabled):
        self._config[key] = enabled

    def start(self, key):
        self._active = _Active(GAME_NAMES[key])

    def stop(self):
        self._active = None

    def is_active(self):
        return self._active is not None


class FakeSkillManager:
    def __init__(self):
        self._config = {"schedule": True, "get_weather": False}
        self._skills = {
            "schedule": {"name": "schedule", "description": "管理安排表", "dirname": "schedule",
                         "parameters": [{"name": "action", "type": "string", "required": True, "description": "动作"}]},
            "get_weather": {"name": "get_weather", "description": "查询天气", "dirname": "weather",
                            "parameters": [{"name": "city", "type": "string", "required": True, "description": "城市"}]},
        }

    def list_skills(self):
        return [{"name": s["name"], "description": s["description"],
                 "enabled": self._config.get(s["name"], True), "dirname": s["dirname"]}
                for s in self._skills.values()]

    def get_skill_detail(self, name):
        s = self._skills.get(name)
        if not s:
            return None
        return {**s, "enabled": self._config.get(name, True)}

    def toggle(self, name, enabled):
        self._config[name] = enabled

    def execute(self, name, args):
        return f"executed {name}"

    def remove_skill(self, name):
        self._skills.pop(name, None)
        return True

    def add_skill(self, path):
        return True, "fake added"

    def add_skill_zip(self, path):
        return True, "fake added"


class FakePet:
    def __init__(self):
        self.game_manager = FakeGameManager()
        self.skill_manager = FakeSkillManager()
        self.start_time = time.time()
        self.root = None


def main():
    pet = FakePet()
    srv = ManagementServer(pet, static_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "dist"))
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
        # 游戏
        st, b = call("GET", "/api/games")
        g = json.loads(b)
        assert st == 200 and len(g["games"]) == 5 and g["active"] is None
        print("1 games list ok (5 games)")

        st, b = call("POST", "/api/games/fly_high/start")
        g = json.loads(b)
        assert g["active"] == "一飞冲天" and [x for x in g["games"] if x["key"] == "fly_high"][0]["active"]
        print("2 game start ok (active=一飞冲天)")

        st, b = call("POST", "/api/games/stop")
        g = json.loads(b)
        assert g["active"] is None
        print("3 game stop ok")

        st, b = call("POST", "/api/games/fishing/toggle", {"enabled": False})
        g = json.loads(b)
        assert [x for x in g["games"] if x["key"] == "fishing"][0]["enabled"] is False
        print("4 game toggle ok")

        # 技能
        st, b = call("GET", "/api/skills")
        s = json.loads(b)
        assert st == 200 and len(s["skills"]) == 2
        print("5 skills list ok")

        st, b = call("GET", "/api/skills/schedule")
        d = json.loads(b)
        assert st == 200 and d["parameters"][0]["name"] == "action"
        assert "name: schedule" in d.get("skillMd", "")
        print("6 skill detail ok (params + SKILL.md)")

        st, b = call("POST", "/api/skills/schedule/toggle", {"enabled": False})
        assert json.loads(b)["ok"] is True
        assert pet.skill_manager._config["schedule"] is False
        print("7 skill toggle ok")

        st, b = call("POST", "/api/skills/get_weather/execute", {"arguments": {"city": "深圳"}})
        assert "executed get_weather" in json.loads(b)["result"]
        print("8 skill execute ok")

        st, b = call("DELETE", "/api/skills/get_weather")
        assert json.loads(b)["ok"] is True
        st, b = call("GET", "/api/skills")
        assert len(json.loads(b)["skills"]) == 1
        print("9 skill delete ok")

        st, b = call("POST", "/api/skills/import",
                     {"filename": "hello.py", "content": base64.b64encode(b"print(1)").decode()})
        r = json.loads(b)
        assert st == 200 and r["ok"] is True, r
        print("10 skill import ok")

        print("ALL PHASE-4 API TESTS PASS")
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
