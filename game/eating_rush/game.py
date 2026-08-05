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
    RULE_TEXT = "这是今天的第…碗？训练员，开动啦！（点任意处或按空格）"
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
        self._food_label: Optional[tk.Label] = None
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
        # 任意位置点击（含桌宠/面板）都算吃；面板作为点击目标，禁用拖动防误拖
        self._set_counter_draggable(False)
        self._bind_all("<Button-1>", self._on_bite)
        self._bind_all("<KeyPress-space>", self._on_bite)
        self._render()
        self._schedule(self.FRAME_MS, self._tick)

    # ── 面板（碗 + 饭量/时间 + 暴食状态） ──
    def _build_counter(self, panel: tk.Frame) -> None:
        self._bowl_canvas = tk.Canvas(panel, width=200, height=70,
                                      bg=cfg.C_BG, highlightthickness=0)
        self._bowl_canvas.grid(row=0, column=0, columnspan=2, padx=8, pady=(6, 2))
        for col, title in enumerate(("饭量", "时间")):
            tk.Label(panel, text=title, font=(cfg.FONT_FAMILY, 9),
                     bg=cfg.C_BG, fg=cfg.C_ASH_DARK).grid(row=1, column=col, padx=8)
        self._food_label = tk.Label(panel, text=f"{EatingRules.TOTAL_FOOD}/{EatingRules.TOTAL_FOOD}",
                                    font=(cfg.FONT_FAMILY, 18, "bold"),
                                    bg=cfg.C_BG, fg=cfg.C_WOOD)
        self._food_label.grid(row=2, column=0, padx=8)
        self._time_label = tk.Label(panel, text=f"{EatingRules.TIME_LIMIT:.0f}",
                                    font=(cfg.FONT_FAMILY, 18, "bold"),
                                    bg=cfg.C_BG, fg=cfg.C_ROSE_DEEP)
        self._time_label.grid(row=2, column=1, padx=8)
        self._boost_label = tk.Label(panel, text="", font=(cfg.FONT_FAMILY, 10, "bold"),
                                     bg=cfg.C_BG, fg=cfg.C_ROSE)
        self._boost_label.grid(row=3, column=0, columnspan=2, pady=(0, 4))
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
            self._maybe_talk(_MILESTONE_TEXTS[self._bite_count], 1200)
        elif self._boost:
            self._maybe_talk(random.choice(_BOOST_TEXTS), 1000)
        elif random.random() < 0.2:
            self._maybe_talk(random.choice(_BITE_TEXTS), 1000)
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
        if getattr(self, "_food_label", None):
            self._food_label.config(text=f"{self.food_left}/{EatingRules.TOTAL_FOOD}")
        if getattr(self, "_time_label", None):
            urgent = self._time_left <= 5
            self._time_label.config(text=f"{self._time_left:.0f}",
                                    fg=cfg.C_ROSE if urgent else cfg.C_ROSE_DEEP)
        if getattr(self, "_boost_label", None):
            self._boost_label.config(text="暴食中！" if self._boost else "")

    def _draw_bowl(self) -> None:
        c = self._bowl_canvas
        if not c:
            return
        c.delete("all")
        c.create_rounded_rectangle(4, 4, 196, 66, radius=16,
                                   fill=cfg.C_WOOD_LIGHT, outline=cfg.C_WOOD)
        ratio = self.food_left / EatingRules.TOTAL_FOOD
        c.create_rounded_rectangle(10, 20, 10 + 176 * ratio, 58, radius=10,
                                   fill=cfg.C_SNOW, outline="")
        c.create_text(28, 34, text="🍚", font=("Segoe UI Emoji", 16))

    # ── 结算 ──────────────────────────────
    def _finish_win(self) -> None:
        self._finished = True
        self._finish(EatingRules.result_tier(0, self._time_left))

    def _finish_end(self) -> None:
        self._finished = True
        self._finish(EatingRules.result_tier(self.food_left, 0))
