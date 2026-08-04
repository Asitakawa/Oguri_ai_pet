"""小游戏：钓鱼时机 — 在浮标进入区间时点击提竿"""
from __future__ import annotations

import random
import tkinter as tk
from typing import Optional

from core import config as cfg
from game.base import BaseGame
from game.rules import FishingRules
from utils.logger import get_logger

log = get_logger("game.fishing")

_PERFECT_TEXTS = ["钓到了！好大一条！", "哇，这条鱼好肥！"]
_NEAR_TEXTS = ["唔…小了点，但也是收获"]
_MISS_TEXTS = ["啊，跑掉了…", "下手太早啦"]
_TIMEOUT_TEXTS = ["训练员，浮标不动了…"]


class FishingGame(BaseGame):
    NAME = "钓鱼时机"
    DESCRIPTION = "在浮标进入区间时点击提竿！"
    RULE_TEXT = "听说这里有很多好吃的鱼…浮标进绿色区间就点一下！"
    FRAME_MS = 33

    def __init__(self, pet) -> None:
        super().__init__(pet)
        self._round_no = 0
        self._points = 0
        self._counts = {"perfect": 0, "near": 0, "miss": 0}
        self._phase = "idle"  # idle / float / result
        self._round_elapsed = 0.0
        self._overlay: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._bobber_id = None

    # ── 生命周期 ──────────────────────────
    def start(self) -> None:
        super().start()
        self._round_no = 0
        self._points = 0
        self._counts = {"perfect": 0, "near": 0, "miss": 0}
        self._phase = "idle"
        self._bind_all("<Button-1>", self._on_cast)
        self._bind_all("<KeyPress-space>", self._on_cast)
        self._create_overlay()
        self._start_round()

    def stop(self) -> None:
        super().stop()
        self._destroy_overlay()

    def _finish_game(self) -> None:
        text = FishingRules.result_tier(self._points)
        text += f"（{self._points} 分）"
        self._finish(text)

    # ── 覆盖层 ────────────────────────────
    def _create_overlay(self) -> None:
        w, h = 360, 520
        x = max(0, (self.pet.screen_w - w) // 2)
        y = max(0, (self.pet.screen_h - h) // 2)
        win = tk.Toplevel(self.pet.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-transparentcolor", "black")
        win.config(bg="black")
        canvas = tk.Canvas(win, width=w, height=h, bg="black", highlightthickness=0)
        canvas.pack()
        win.geometry(f"{w}x{h}+{x}+{y}")
        self._overlay = win
        self._canvas = canvas
        if self._counter_win:
            self._counter_win.lift()
        self._draw_static()

    def _destroy_overlay(self) -> None:
        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None
            self._canvas = None
            self._bobber_id = None

    # ── 回合状态机 ────────────────────────
    def _start_round(self) -> None:
        self._round_no += 1
        self._phase = "float"
        self._round_elapsed = 0.0
        self._draw_static()
        self._update_counter(f"第 {self._round_no}/{FishingRules.TOTAL_ROUNDS} 回合  {self._points} 分")
        self._schedule(int(FishingRules.ROUND_SECONDS * 1000), self._on_timeout)
        self._schedule(self.FRAME_MS, self._animate)

    def _animate(self) -> None:
        if not self._active or self._phase != "float":
            return
        self._round_elapsed += self.FRAME_MS / 1000.0
        by = FishingRules.bobber_y(self._round_elapsed)
        if self._canvas and self._bobber_id:
            self._canvas.coords(self._bobber_id, 180, by)
        self._schedule(self.FRAME_MS, self._animate)

    def _on_cast(self, event=None) -> None:
        if not self._active or self._phase != "float":
            return
        by = FishingRules.bobber_y(self._round_elapsed)
        offset = by - FishingRules.CENTER_Y
        judgment = FishingRules.judge(offset, FishingRules.zone_half(self._round_no))
        self._counts[judgment] += 1
        if judgment == "perfect":
            fish, val = FishingRules.reward(judgment)
            self._points += val
            if self._canvas and self._bobber_id:
                self._canvas.itemconfig(self._bobber_id, text=fish)
            self._talk(random.choice(_PERFECT_TEXTS), 1800)
            self.pet.tilt_head()
        elif judgment == "near":
            fish, val = FishingRules.reward(judgment)
            self._points += val
            if self._canvas and self._bobber_id:
                self._canvas.itemconfig(self._bobber_id, text=fish)
            self._talk(random.choice(_NEAR_TEXTS), 1500)
        else:
            self._talk(random.choice(_MISS_TEXTS), 1500)
        self._phase = "result"
        self._update_counter(f"第 {self._round_no}/{FishingRules.TOTAL_ROUNDS} 回合  {self._points} 分")
        if self._round_no >= FishingRules.TOTAL_ROUNDS:
            self._schedule(int(FishingRules.RESULT_SECONDS * 1000), self._finish_game)
        else:
            self._schedule(int(FishingRules.RESULT_SECONDS * 1000), self._next_round)

    def _on_timeout(self) -> None:
        if not self._active or self._phase != "float":
            return
        self._counts["miss"] += 1
        self._talk(random.choice(_TIMEOUT_TEXTS), 1500)
        self._phase = "result"
        if self._round_no >= FishingRules.TOTAL_ROUNDS:
            self._schedule(int(FishingRules.RESULT_SECONDS * 1000), self._finish_game)
        else:
            self._schedule(int(FishingRules.RESULT_SECONDS * 1000), self._next_round)

    def _next_round(self) -> None:
        if not self._active:
            return
        self._start_round()

    # ── 绘制 ──────────────────────────────
    def _draw_static(self) -> None:
        c = self._canvas
        if not c:
            return
        c.delete("all")
        zh = FishingRules.zone_half(self._round_no)
        c.create_rectangle(20, FishingRules.CENTER_Y - zh, 340, FishingRules.CENTER_Y + zh,
                           fill=cfg.C_MINT, stipple="gray50", outline=cfg.C_MINT_DEEP, width=2)
        c.create_line(20, FishingRules.CENTER_Y, 340, FishingRules.CENTER_Y,
                      fill=cfg.C_ASH_LIGHT, dash=(4, 4))
        for yy in (70, 450):
            c.create_line(20, yy, 340, yy, fill=cfg.C_SKY, width=3)
        c.create_text(180, 40, text="🎣 钓鱼",
                      font=(cfg.FONT_FAMILY, 13, "bold"), fill=cfg.C_WOOD)
        self._bobber_id = c.create_text(180, FishingRules.CENTER_Y, text="🎣",
                                        font=("Segoe UI Emoji", 30))
