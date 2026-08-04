"""小游戏：大胃王速吃 — 连点把一碗饭吃完"""
from __future__ import annotations

import random
import time
import tkinter as tk
from typing import List, Optional

import utils.tk_ext  # noqa: F401  确保 Canvas 圆角扩展可用
from core import config as cfg
from game.base import BaseGame
from game.rules import EatingRules
from utils.logger import get_logger

log = get_logger("game.eating")

_BITE_TEXTS = ["好吃…", "再来一口！", "啊呜！", "软软的"]
_BOOST_TEXTS = ["根本停不下来！", "喉咙在唱歌！"]
_MILESTONE_TEXTS = {5: "训练员喂得好快！", 10: "一半了！但还只是开胃！",
                    15: "碗要见底了！", 20: "最后一口气！咕咚咕咚！"}


class EatingRushGame(BaseGame):
    NAME = "大胃王速吃"
    DESCRIPTION = "限时狂点，把一碗饭吃完！"
    RULE_TEXT = "这是今天的第…碗？训练员，开动啦！"
    FRAME_MS = 100

    def __init__(self, pet) -> None:
        super().__init__(pet)
        self.food_left = EatingRules.TOTAL_FOOD
        self._clicks: List[float] = []
        self._boost = False
        self._bite_count = 0
        self._time_left = EatingRules.TIME_LIMIT
        self._finished = False
        self._bowl_canvas: Optional[tk.Canvas] = None
        self._rice_label: Optional[tk.Label] = None
        self._time_label: Optional[tk.Label] = None
        self._boost_label: Optional[tk.Label] = None

    # ── 生命周期 ──────────────────────────
    def start(self) -> None:
        super().start()
        self.food_left = EatingRules.TOTAL_FOOD
        self._clicks = []
        self._boost = False
        self._bite_count = 0
        self._time_left = EatingRules.TIME_LIMIT
        self._finished = False
        self._bind(self.pet.label, "<Button-1>", self._on_bite)
        self._bind_all("<KeyPress-space>", self._on_bite)
        self._render()
        self._schedule(self.FRAME_MS, self._tick)

    def _build_counter(self, panel: tk.Frame) -> None:
        self._bowl_canvas = tk.Canvas(panel, width=180, height=64,
                                      bg=cfg.C_BG, highlightthickness=0)
        self._bowl_canvas.pack(padx=8, pady=(6, 2))
        self._rice_label = tk.Label(panel, text="", font=("Segoe UI Emoji", 14), bg=cfg.C_BG)
        self._rice_label.pack()
        self._time_label = tk.Label(panel, text="", font=(cfg.FONT_FAMILY, 12, "bold"),
                                    bg=cfg.C_BG, fg=cfg.C_ROSE_DEEP)
        self._time_label.pack()
        self._boost_label = tk.Label(panel, text="", font=(cfg.FONT_FAMILY, 10),
                                     bg=cfg.C_BG, fg=cfg.C_ROSE)
        self._boost_label.pack()
        self._counter_label = self._time_label

    # ── 交互 ──────────────────────────────
    def _on_bite(self, event=None) -> None:
        if not self._active or self._finished:
            return
        now = time.time()
        self._clicks = [t for t in self._clicks if now - t <= 1.0]
        self._clicks.append(now)
        rate = len(self._clicks)
        if rate > EatingRules.MAX_RATE:
            return  # 反宏：超出频率上限不计
        self._boost = EatingRules.is_boost(rate)
        self.food_left = max(0, self.food_left - EatingRules.damage(self._boost))
        self._bite_count += 1
        self.pet._set_pet_image("click", auto_reset=250)
        if self._bite_count % 3 == 0:
            self.pet.eat_action()
        self._render()
        if self._bite_count % 5 == 0 and self._bite_count in _MILESTONE_TEXTS:
            self._talk(_MILESTONE_TEXTS[self._bite_count], 1200)
        if self._boost:
            self._talk(random.choice(_BOOST_TEXTS), 1000)
        elif random.random() < 0.2:
            self._talk(random.choice(_BITE_TEXTS), 1000)
        if self.food_left <= 0:
            self._finish_win()

    def _tick(self) -> None:
        if not self._active or self._finished:
            return
        self._time_left -= self.FRAME_MS / 1000.0
        if self._time_left <= 0:
            self._time_left = 0
            self._finish_end()
            return
        self._render()
        self._schedule(self.FRAME_MS, self._tick)

    # ── 渲染 ──────────────────────────────
    def _render(self) -> None:
        if self._bowl_canvas:
            self._draw_bowl()
        if self._rice_label:
            self._rice_label.config(text="🍚" * EatingRules.rice_count(self.food_left))
        if self._time_label:
            urgent = self._time_left <= 5
            self._time_label.config(
                text=f"⏱ {self._time_left:.0f}s",
                fg=cfg.C_ROSE if urgent else cfg.C_ROSE_DEEP)
        if self._boost_label:
            self._boost_label.config(text="🔥 暴食中！" if self._boost else "")

    def _draw_bowl(self) -> None:
        c = self._bowl_canvas
        if not c:
            return
        c.delete("all")
        c.create_rounded_rectangle(4, 4, 176, 60, radius=16,
                                   fill=cfg.C_WOOD_LIGHT, outline=cfg.C_WOOD)
        ratio = self.food_left / EatingRules.TOTAL_FOOD
        c.create_rounded_rectangle(10, 18, 10 + 156 * ratio, 52, radius=10,
                                   fill=cfg.C_SNOW, outline="")
        c.create_text(90, 46, text=f"{self.food_left}/{EatingRules.TOTAL_FOOD}",
                      font=(cfg.FONT_FAMILY, 10, "bold"), fill=cfg.C_WOOD)

    # ── 结算 ──────────────────────────────
    def _finish_win(self) -> None:
        self._finished = True
        self._finish(EatingRules.result_tier(0, self._time_left))

    def _finish_end(self) -> None:
        self._finished = True
        self._finish(EatingRules.result_tier(self.food_left, 0))
