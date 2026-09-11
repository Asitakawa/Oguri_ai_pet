"""小游戏：钓鱼时机 — 在浮标进入区间时点击提竿"""
from __future__ import annotations

import random
import tkinter as tk
from typing import List, Optional

from core import config as cfg
from game.base import BaseGame
from game.rules import FishingRules
from utils.logger import get_logger

log = get_logger("game.fishing")

_PERFECT_TEXTS = ["钓到了！好大一条！", "哇，这条鱼好肥！"]
_NEAR_TEXTS = ["唔…小了点，但也是收获"]
_MISS_TEXTS = ["啊，跑掉了…", "下手太早啦"]
_TIMEOUT_TEXTS = ["训练员，浮标不动了…"]

_LINE_TOP = 48          # 鱼线顶端（竿下）
_FLOAT_TICK = 66        # 飘字刷新间隔 ms
_FLOAT_LIFE = 0.8       # 飘字存活秒数


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
        self._wave_phase = 0.0  # 浮标正弦初相位（每回合重新随机）
        self._float_texts: List[dict] = []
        self._overlay: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._bobber_id = None
        self._line_id = None
        self._round_label: Optional[tk.Label] = None
        self._points_label: Optional[tk.Label] = None
        self._status_label: Optional[tk.Label] = None

    # ── 生命周期 ──────────────────────────
    def start(self) -> None:
        super().start()
        self._round_no = 0
        self._points = 0
        self._counts = {"perfect": 0, "near": 0, "miss": 0}
        self._phase = "idle"
        self._float_texts = []
        self._set_counter_draggable(False)  # 点击都算提竿，避免拖动误触
        self._bind_all("<Button-1>", self._on_cast)
        self._bind_all("<KeyPress-space>", self._on_cast)
        self._create_overlay()
        self._schedule(_FLOAT_TICK, self._float_tick)
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
        x = int(self.pet.x + self.pet.pet_size[0] // 2 - w // 2)
        x = max(0, min(x, self.pet.screen_w - w))
        y = int(self.pet.y) - h - 20  # 浮在桌宠上方，避免遮挡桌宠
        y = max(0, y)
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
            self._line_id = None

    # ── 面板（回合/得分 + 判定状态） ────────
    def _build_counter(self, panel: tk.Frame) -> None:
        for col, title in enumerate(("回合", "得分")):
            tk.Label(panel, text=title, font=(cfg.FONT_FAMILY, 9),
                     bg=cfg.C_BG, fg=cfg.C_ASH_DARK).grid(row=0, column=col, padx=10, pady=(6, 0))
        self._round_label = tk.Label(panel, text=f"0/{FishingRules.TOTAL_ROUNDS}",
                                     font=(cfg.FONT_FAMILY, 20, "bold"),
                                     bg=cfg.C_BG, fg=cfg.C_SKY_DEEP)
        self._round_label.grid(row=1, column=0, padx=10)
        self._points_label = tk.Label(panel, text="0", font=(cfg.FONT_FAMILY, 20, "bold"),
                                      bg=cfg.C_BG, fg=cfg.C_MINT_DEEP)
        self._points_label.grid(row=1, column=1, padx=10)
        self._status_label = tk.Label(panel, text="", font=(cfg.FONT_FAMILY, 9),
                                      bg=cfg.C_BG, fg=cfg.C_ASH_DARK)
        self._status_label.grid(row=2, column=0, columnspan=2, pady=(0, 4))
        self._counter_label = self._points_label

    def _render_counter(self) -> None:
        if getattr(self, "_round_label", None):
            self._round_label.config(text=f"{self._round_no}/{FishingRules.TOTAL_ROUNDS}")
        if getattr(self, "_points_label", None):
            self._points_label.config(text=str(self._points))

    def _set_status(self, text: str, fg: str = None) -> None:
        if getattr(self, "_status_label", None):
            self._status_label.config(text=text, fg=fg or cfg.C_ASH_DARK)

    # ── 回合状态机 ────────────────────────
    def _start_round(self) -> None:
        self._round_no += 1
        self._phase = "float"
        self._round_elapsed = 0.0
        # 每回合随机初相位，且保证开局浮标不在区间内——
        # 否则 sin(0)=0 让开局位置恒为区间正中，「立刻点」每回合必中 perfect
        self._wave_phase = FishingRules.random_phase(self._round_no)
        self._set_status("")
        self._draw_static()
        self._render_counter()
        round_no = self._round_no
        self._schedule(int(FishingRules.ROUND_SECONDS * 1000),
                       lambda r=round_no: self._on_timeout(r))
        self._schedule(self.FRAME_MS, self._animate)

    def _animate(self) -> None:
        if not self._active or self._phase != "float":
            return
        self._round_elapsed += self.FRAME_MS / 1000.0
        by = FishingRules.bobber_y(self._round_elapsed, self._round_no, self._wave_phase)
        if self._canvas and self._bobber_id:
            self._canvas.coords(self._bobber_id, 180, by)
        if self._canvas and self._line_id:
            self._canvas.coords(self._line_id, 180, _LINE_TOP, 180, by)
        self._schedule(self.FRAME_MS, self._animate)

    def _on_cast(self, event=None) -> None:
        if not self._active or self._phase != "float":
            return
        by = FishingRules.bobber_y(self._round_elapsed, self._round_no, self._wave_phase)
        offset = by - FishingRules.CENTER_Y
        judgment = FishingRules.judge(offset, FishingRules.zone_half(self._round_no))
        self._counts[judgment] += 1
        bx, by2 = 180, by
        if judgment == "perfect":
            fish, val = FishingRules.reward(judgment)
            self._points += val
            if self._canvas and self._bobber_id:
                self._canvas.itemconfig(self._bobber_id, text=fish)
            self._spawn_float(bx, by2 - 16, f"+{val}", cfg.C_MINT_DEEP)
            self._set_status(f"正中！{fish} +{val}", cfg.C_MINT_DEEP)
            self._talk(random.choice(_PERFECT_TEXTS), 1800)
            bounce = getattr(self.pet, "start_bounce_animation", None)
            if bounce:
                bounce()
            else:
                self.pet.tilt_head()
        elif judgment == "near":
            fish, val = FishingRules.reward(judgment)
            self._points += val
            if self._canvas and self._bobber_id:
                self._canvas.itemconfig(self._bobber_id, text=fish)
            self._spawn_float(bx, by2 - 16, f"+{val}", cfg.C_SKY_DEEP)
            self._set_status(f"擦边 {fish} +{val}", cfg.C_SKY_DEEP)
            self._talk(random.choice(_NEAR_TEXTS), 1500)
        else:
            self._spawn_float(bx, by2 - 16, "×", cfg.C_ASH)
            self._set_status("落空…", cfg.C_ASH)
            self._talk(random.choice(_MISS_TEXTS), 1500)
        self._phase = "result"
        self._render_counter()
        if self._round_no >= FishingRules.TOTAL_ROUNDS:
            self._schedule(int(FishingRules.RESULT_SECONDS * 1000), self._finish_game)
        else:
            self._schedule(int(FishingRules.RESULT_SECONDS * 1000), self._next_round)

    def _on_timeout(self, round_no: int) -> None:
        if not self._active or round_no != self._round_no or self._phase != "float":
            return
        self._counts["miss"] += 1
        self._spawn_float(180, FishingRules.CENTER_Y - 16, "×", cfg.C_ASH)
        self._set_status("超时…", cfg.C_ASH)
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

    # ── 飘字反馈 ──────────────────────────
    def _spawn_float(self, x: float, y: float, text: str, color: str) -> None:
        self._float_texts.append({"x": x, "y": y, "text": text, "color": color, "age": 0.0})

    def _float_tick(self) -> None:
        if not self._active:
            return
        self._update_floats(_FLOAT_TICK / 1000.0)
        self._schedule(_FLOAT_TICK, self._float_tick)

    def _update_floats(self, dt: float) -> None:
        c = self._canvas
        if not c:
            return
        c.delete("float")
        for ft in self._float_texts:
            ft["age"] += dt
            ft["y"] -= 30 * dt
            if ft["age"] < _FLOAT_LIFE:
                c.create_text(ft["x"], ft["y"], text=ft["text"], fill=ft["color"],
                              font=(cfg.FONT_FAMILY, 14, "bold"), tags="float")
        self._float_texts = [ft for ft in self._float_texts if ft["age"] < _FLOAT_LIFE]

    # ── 绘制 ──────────────────────────────
    def _draw_static(self) -> None:
        c = self._canvas
        if not c:
            return
        c.delete("all")
        zh = FishingRules.zone_half(self._round_no)
        # 起始位置也要按本回合相位算，否则会先画在正中再跳到真实位置
        y0 = FishingRules.bobber_y(0.0, self._round_no, self._wave_phase)
        c.create_rectangle(20, FishingRules.CENTER_Y - zh, 340, FishingRules.CENTER_Y + zh,
                           fill=cfg.C_MINT, stipple="gray50", outline=cfg.C_MINT_DEEP, width=2)
        c.create_line(20, FishingRules.CENTER_Y, 340, FishingRules.CENTER_Y,
                      fill=cfg.C_ASH_LIGHT, dash=(4, 4))
        for yy in (70, 450):
            c.create_line(20, yy, 340, yy, fill=cfg.C_SKY, width=3)
        c.create_text(180, 34, text="钓鱼", font=(cfg.FONT_FAMILY, 13, "bold"), fill=cfg.C_WOOD)
        self._line_id = c.create_line(180, _LINE_TOP, 180, y0,
                                      fill=cfg.C_ASH, width=2, tags="line")
        self._bobber_id = c.create_text(180, y0, text="🎣",
                                        font=("Segoe UI Emoji", 30))
