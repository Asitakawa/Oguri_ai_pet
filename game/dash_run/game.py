"""小游戏：冲刺障碍跑 — 跳跃躲避障碍"""
from __future__ import annotations

import random
import tkinter as tk
from typing import List, Optional

import utils.tk_ext  # noqa: F401  确保 Canvas 圆角扩展可用
from core import config as cfg
from game.base import BaseGame
from game.rules import DashRules
from utils.logger import get_logger

log = get_logger("game.dash")

_HIT_TEXTS = ["呜哇！被绊到了…", "啊！那个是石头吗"]
_KIND_STYLE = {
    "hurdle": {"color": cfg.C_WOOD_LIGHT, "emoji": "🚧"},
    "rock":   {"color": cfg.C_ASH,        "emoji": "🪨"},
    "wall":   {"color": cfg.C_ROSE_DEEP,  "emoji": "🧱"},
    "tree":   {"color": cfg.C_MINT_DEEP,  "emoji": "🌲"},
    "bird":   {"color": cfg.C_SKY_DEEP,   "emoji": "🐦"},
}


class DashRunGame(BaseGame):
    NAME = "冲刺障碍跑"
    DESCRIPTION = "跳跃躲避障碍，跑得越远越好！"
    RULE_TEXT = "前方就是终点！空格或点击起跳，躲开障碍！"
    FRAME_MS = 33

    def __init__(self, pet) -> None:
        super().__init__(pet)
        self._speed = DashRules.BASE_SPEED
        self._obstacles: List[dict] = []
        self._distance_px = 0.0
        self._elapsed = 0.0
        self._vy = 0.0
        self._on_ground = True
        self._hitting = False
        self._ground_line = 0.0
        self._fixed_x = 0
        self._spawn_cd = DashRules.FIRST_GAP_S
        self._last_kind: Optional[str] = None
        self._overlay: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None

    # ── 生命周期 ──────────────────────────
    def start(self) -> None:
        super().start()
        pet_h = self.pet.pet_size[1]
        self._ground_line = float(self.pet.screen_h) - 60  # 保留任务栏间距
        self._fixed_x = int(self.pet.screen_w * 0.22)
        self.pet.x = self._fixed_x
        self.pet.y = self._ground_line - pet_h
        self.pet._move()
        self._speed = DashRules.BASE_SPEED
        self._obstacles = []
        self._distance_px = 0.0
        self._elapsed = 0.0
        self._vy = 0.0
        self._on_ground = True
        self._hitting = False
        self._spawn_cd = DashRules.FIRST_GAP_S
        self._last_kind = None
        self._bind_all("<Button-1>", self._on_jump)
        self._bind_all("<KeyPress-space>", self._on_jump)
        self._create_overlay()
        self._schedule(self.FRAME_MS, self._update)

    def stop(self) -> None:
        super().stop()
        self._destroy_overlay()

    def _finish_game(self) -> None:
        meters = self._distance_px / DashRules.PX_PER_METER
        self._finish(f"{DashRules.distance_tier(meters)}（{int(meters)} 米）")

    # ── 覆盖层 ────────────────────────────
    def _create_overlay(self) -> None:
        win = tk.Toplevel(self.pet.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-transparentcolor", "black")
        win.config(bg="black")
        canvas = tk.Canvas(win, width=self.pet.screen_w, height=self.pet.screen_h,
                           bg="black", highlightthickness=0)
        canvas.pack()
        win.geometry(f"{self.pet.screen_w}x{self.pet.screen_h}+0+0")
        self._overlay = win
        self._canvas = canvas
        if self._counter_win:
            self._counter_win.lift()
        canvas.bind("<Button-3>", self._on_menu)

    def _on_menu(self, event) -> None:
        show = getattr(self.pet, "_show_menu", None)
        if show:
            show(event)

    def _destroy_overlay(self) -> None:
        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None
            self._canvas = None

    # ── 交互 ──────────────────────────────
    def _on_jump(self, event=None) -> None:
        if not self._active or self._hitting:
            return
        if self._on_ground:
            self._vy = DashRules.JUMP_V
            self._on_ground = False
            self.pet._set_pet_image("click", auto_reset=400)

    # ── 主循环 ────────────────────────────
    def _update(self) -> None:
        if not self._active:
            return
        if self._hitting:
            return  # 等待结算回调
        dt = self.FRAME_MS / 1000.0
        self._elapsed += dt
        self._speed = DashRules.speed_at(self._elapsed)
        ground_y = self._ground_line - self.pet.pet_size[1]
        self.pet.y, self._vy, self._on_ground = DashRules.step_vertical(
            self.pet.y, self._vy, self._on_ground, ground_y)
        self.pet._move()
        self._distance_px += self._speed
        # 按时间间隔生成障碍（保证任意速度下的反应时间）
        self._spawn_cd -= dt
        if self._spawn_cd <= 0:
            self._spawn_obstacle()
            self._spawn_cd = random.uniform(DashRules.MIN_GAP_S, DashRules.MAX_GAP_S)
        hit = self._step_obstacles()
        self._draw_ground()
        meters = self._distance_px / DashRules.PX_PER_METER
        self._update_counter(f"{int(meters)} 米  速度{self._speed:.0f}")
        if hit is not None:
            self._on_hit(hit)
            return
        self._schedule(self.FRAME_MS, self._update)

    def _spawn_obstacle(self) -> None:
        kind = DashRules.pick_obstacle(self._elapsed, self._last_kind)
        self._last_kind = kind
        self._obstacles.extend(DashRules.obstacle_rects(
            kind, self.pet.screen_w + 20, self._ground_line,
            self._speed, self.pet.pet_size[1]))

    def _step_obstacles(self):
        c = self._canvas
        if not c:
            return None
        c.delete("obs")
        pet_box = DashRules.pet_hitbox(self.pet.x, self.pet.y,
                                       self.pet.pet_size[0], self.pet.pet_size[1])
        hit = None
        for ob in self._obstacles:
            ob["x"] -= self._speed
            self._draw_obstacle(ob)
            if hit is None and DashRules.collides(*pet_box, ob["x"], ob["y"], ob["w"], ob["h"]):
                hit = ob
        self._obstacles = [ob for ob in self._obstacles if ob["x"] + ob["w"] > -20]
        return hit

    def _draw_obstacle(self, ob: dict) -> None:
        c = self._canvas
        if not c:
            return
        style = _KIND_STYLE.get(ob["kind"], _KIND_STYLE["hurdle"])
        c.create_rounded_rectangle(ob["x"], ob["y"], ob["x"] + ob["w"], ob["y"] + ob["h"],
                                   radius=6, fill=style["color"], outline="", tags="obs")
        if ob["kind"] == "bird":
            c.create_text(ob["x"] + ob["w"] // 2, ob["y"] + ob["h"] // 2,
                          text=style["emoji"], font=("Segoe UI Emoji", 18), tags="obs")
        else:
            c.create_text(ob["x"] + ob["w"] // 2, ob["y"] - 12,
                          text=style["emoji"], font=("Segoe UI Emoji", 16), tags="obs")

    def _draw_ground(self) -> None:
        c = self._canvas
        if not c:
            return
        c.delete("ground")
        gy = self._ground_line
        c.create_line(0, gy, self.pet.screen_w, gy, fill=cfg.C_WOOD, width=3, tags="ground")
        off = (self._distance_px * 0.5) % 60
        for i in range(0, int(self.pet.screen_w // 60) + 2):
            sx = i * 60 - off
            c.create_line(sx, gy, sx - 20, gy, fill=cfg.C_WOOD_LIGHT, width=3, tags="ground")

    def _on_hit(self, ob: dict) -> None:
        self._hitting = True
        self.pet._set_pet_image("click")
        self.pet.tilt_head()
        self._talk(random.choice(_HIT_TEXTS), 1500)
        self._schedule(900, self._finish_game)
