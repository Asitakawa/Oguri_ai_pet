"""小游戏：接饭团 — 移动桌宠接住掉落食物"""
from __future__ import annotations

import math
import random
import tkinter as tk
from typing import List, Optional

from core import config as cfg
from game.base import BaseGame
from game.rules import CatchRules
from utils.logger import get_logger

log = get_logger("game.onigiri")

_EMOJI_FONT = ("Segoe UI Emoji", 28)
_FLOAT_FONT = (cfg.FONT_FAMILY, 14, "bold")
_CATCH_TEXTS = {
    "onigiri": ["啊呜！", "好吃！", "再来一个！"],
    "sushi": ["是高级寿司！好幸福～"],
    "carrot": ["胡萝卜也喜欢！"],
    "star": ["闪闪的，是不是有好事？"],
    "bad": ["呜哇！石头！呸呸呸"],
}
_COMBO_TEXTS = ["停不下来了！", "饭团都往我嘴里飞！", "好撑…但还能接！"]
_MISS_TEXTS = ["没接住…", "对不起…我太专心吃了"]


class OnigiriCatchGame(BaseGame):
    NAME = "接饭团"
    DESCRIPTION = "移动桌宠，接住从天而降的饭团！"
    RULE_TEXT = "训练员，饭团掉下来了！移动我来接住它们！（空格暂停）"
    GAME_SECONDS = 60
    BOTTOM_MARGIN = 60      # 桌宠底部与屏幕底的间距（避开任务栏）
    FOLLOW_LERP = 0.35      # 指针跟随平滑系数（每帧逼近比例）
    FLOAT_LIFE = 0.7        # 飘字存活秒数

    def __init__(self, pet) -> None:
        super().__init__(pet)
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.caught = 0
        self.missed = 0
        self._items: List[dict] = []
        self._float_texts: List[dict] = []
        self._elapsed = 0.0
        self._spawn_timer = 0.0
        self._speed_mult = 1.0
        self._interval = CatchRules.BASE_INTERVAL
        self._phase = 0
        self._paused = False
        self._target_x = 0.0
        self._overlay: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None

    # ── 生命周期 ──────────────────────────
    def start(self) -> None:
        super().start()
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.caught = 0
        self.missed = 0
        self._items = []
        self._float_texts = []
        self._elapsed = 0.0
        self._spawn_timer = 0.0
        self._speed_mult = 1.0
        self._interval = CatchRules.BASE_INTERVAL
        self._phase = 0
        self._paused = False
        # 桌宠放到底部中央（保留任务栏间距）
        self.pet.y = self.pet.screen_h - self.pet.pet_size[1] - self.BOTTOM_MARGIN
        self.pet.x = max(0, (self.pet.screen_w - self.pet.pet_size[0]) // 2)
        self._target_x = float(self.pet.x)
        self.pet._move()
        self._create_overlay()
        self._bind_all("<KeyPress-space>", self._toggle_pause)
        self._schedule(self.FRAME_MS, self._update)

    def stop(self) -> None:
        super().stop()
        self._destroy_overlay()

    def _finish_game(self) -> None:
        text = CatchRules.score_tier(self.score)
        text += f"（接到 {self.caught} 个，漏掉 {self.missed} 个）"
        self._finish(text)

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
        self._make_click_through(win)
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

    # ── 主循环 ────────────────────────────
    def _update(self) -> None:
        if not self._active:
            return
        if self._paused:
            self._update_counter("⏸ 已暂停（空格继续）")
            self._schedule(self.FRAME_MS, self._update)
            return
        dt = self.FRAME_MS / 1000.0
        self._elapsed += dt
        remaining = self.GAME_SECONDS - self._elapsed
        phase = int(self._elapsed // CatchRules.SPEEDUP_EVERY)
        if phase != self._phase:
            self._phase = phase
            self._speed_mult *= CatchRules.SPEEDUP_FACTOR
            self._interval = max(CatchRules.MIN_INTERVAL, self._interval * 0.9)
        self._follow_pointer()
        self._spawn_timer -= dt
        if self._spawn_timer <= 0 and len(self._items) < CatchRules.MAX_ITEMS:
            self._spawn_item()
            self._spawn_timer = self._interval
        self._step_items()
        self._update_float_texts(dt)
        if remaining <= 0:
            self._finish_game()
            return
        self._update_counter(f"{self.score} 分  {int(remaining)}s  🔥{self.max_combo}")
        self._schedule(self.FRAME_MS, self._update)

    def _toggle_pause(self, event=None) -> None:
        if not self._active:
            return
        self._paused = not self._paused
        if self._paused:
            self._talk("⏸ 暂停中…按空格继续", 2500)
        else:
            self._talk("继续！", 1200)

    # ── 桌宠跟随（平滑） ───────────────────
    def _follow_pointer(self) -> None:
        try:
            mx = self.pet.root.winfo_pointerx()
        except Exception:
            return
        target = mx - self.pet.pet_size[0] // 2
        target = max(0, min(target, self.pet.screen_w - self.pet.pet_size[0]))
        self._target_x = float(target)
        dx = target - self.pet.x
        if abs(dx) > 1:
            self.pet.x += dx * self.FOLLOW_LERP
            self.pet._move()

    # ── 掉落物 ────────────────────────────
    def _spawn_item(self) -> None:
        item = CatchRules.pick_item()
        item["x"] = random.uniform(20, max(21, self.pet.screen_w - 20))
        item["y"] = -20.0
        item["phase"] = random.uniform(0, math.pi * 2)
        item["dead"] = False
        self._items.append(item)

    def _step_items(self) -> None:
        if not self._canvas:
            return
        self._canvas.delete("items")
        pet_top = self.pet.y
        for it in self._items:
            it["y"] += it["speed"] * self._speed_mult * CatchRules.BASE_VY
            if it.get("drift"):
                it["phase"] += 0.08
                it["x"] += math.sin(it["phase"]) * it["drift"]
            if CatchRules.would_catch(self.pet.x, self.pet.pet_size[0],
                                      it["x"], it["y"], pet_top):
                self._on_catch(it)
                it["dead"] = True
                continue
            if it["y"] > self.pet.screen_h + 20:
                if it["kind"] != "bad":
                    self._on_miss(it["x"])
                it["dead"] = True
                continue
            self._canvas.create_text(it["x"], it["y"], text=it["emoji"],
                                     font=_EMOJI_FONT, fill="white", tags="items")
        self._items = [it for it in self._items if not it.get("dead")]

    def _on_catch(self, item: dict) -> None:
        self.score += item["value"]
        self.caught += 1
        self.combo += 1
        self.max_combo = max(self.max_combo, self.combo)
        self.pet._set_pet_image("click", auto_reset=300)
        bounce = getattr(self.pet, "start_bounce_animation", None)
        if bounce:
            bounce()
        color = cfg.C_ROSE if item["value"] < 0 else cfg.C_MINT_DEEP
        label = str(item["value"]) if item["value"] < 0 else f"+{item['value']}"
        self._spawn_float_text(item["x"], self.pet.y - 14, label, color)
        if item["kind"] == "bad" or item["value"] >= 2 or self.combo % 2 == 1:
            self._maybe_talk(random.choice(_CATCH_TEXTS.get(item["kind"], ["啊呜！"])), 1500)
        if self.combo in (5, 10, 15):
            self._talk(_COMBO_TEXTS[self.combo // 5 - 1], 1800)

    def _on_miss(self, x: float) -> None:
        self.missed += 1
        self.combo = 0
        self._spawn_float_text(x, self.pet.y - 14, "×", cfg.C_ASH)
        if self.missed in (1, 3, 6):
            self._maybe_talk(_MISS_TEXTS[0 if self.missed == 1 else 1], 1500)

    # ── 飘字反馈 ──────────────────────────
    def _spawn_float_text(self, x: float, y: float, text: str, color: str) -> None:
        self._float_texts.append({"x": x, "y": y, "text": text, "color": color, "age": 0.0})

    def _update_float_texts(self, dt: float) -> None:
        c = self._canvas
        if not c:
            return
        c.delete("float")
        for ft in self._float_texts:
            ft["age"] += dt
            ft["y"] -= 34 * dt
            if ft["age"] < self.FLOAT_LIFE:
                c.create_text(ft["x"], ft["y"], text=ft["text"], fill=ft["color"],
                              font=_FLOAT_FONT, tags="float")
        self._float_texts = [ft for ft in self._float_texts if ft["age"] < self.FLOAT_LIFE]
