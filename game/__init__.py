"""小游戏管理器 — 每个游戏独立，仅在游玩时生效"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from core.paths import get_data_path
from game.base import BaseGame  # noqa: F401
from game.dash_run.game import DashRunGame
from game.eating_rush.game import EatingRushGame
from game.fishing.game import FishingGame
from game.fly_high.game import FlyHighGame
from game.onigiri_catch.game import OnigiriCatchGame
from utils.logger import get_logger

log = get_logger("game")


# 游戏注册表：key -> (名称, 游戏类)
GAMES: Dict[str, Dict[str, object]] = {
    "fly_high": {"name": "一飞冲天", "desc": "用力把我抛起来吧！", "cls": FlyHighGame},
    "onigiri_catch": {"name": "接饭团", "desc": "移动桌宠接住掉落的饭团", "cls": OnigiriCatchGame},
    "eating_rush": {"name": "大胃王速吃", "desc": "限时狂点吃完一碗饭", "cls": EatingRushGame},
    "dash_run": {"name": "冲刺障碍跑", "desc": "跳跃躲避障碍，跑得越远越好", "cls": DashRunGame},
    "fishing": {"name": "钓鱼时机", "desc": "在浮标进入区间时点击提竿", "cls": FishingGame},
}


class GameManager:
    def __init__(self, pet) -> None:
        self.pet = pet
        self._config_path = get_data_path("games.json")
        self._config: Dict[str, bool] = {}
        self._active = None
        self._load()

    def _load(self) -> None:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except Exception:
            self._config = {}

    def _save(self) -> None:
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("游戏配置保存失败: %s", e)

    def is_enabled(self, key: str) -> bool:
        return self._config.get(key, True)

    def set_enabled(self, key: str, enabled: bool) -> None:
        self._config[key] = enabled
        self._save()

    def list_enabled(self) -> List[Tuple[str, str]]:
        return [(k, v["name"]) for k, v in GAMES.items() if self.is_enabled(k)]  # type: ignore[return-value]

    def list_all(self) -> List[Tuple[str, str, bool]]:
        return [(k, v["name"], self.is_enabled(k)) for k, v in GAMES.items()]  # type: ignore[return-value]

    def is_active(self) -> bool:
        return self._active is not None

    def start(self, key: str) -> None:
        if key not in GAMES:
            return
        if self._active:
            self.stop()
        game = GAMES[key]["cls"](self.pet)  # type: ignore[misc]
        self._active = game
        game.start()

    def stop(self) -> None:
        if self._active:
            self._active.stop()
            self._active = None
