"""小游戏：一飞冲天 — 仿古早 QQ 宠物抛高游戏"""
from __future__ import annotations

import tkinter as tk

from core import config as cfg


class FlyHighGame:
    NAME = "一飞冲天"
    DESCRIPTION = "用力把我抛起来吧！看看能飞多高"
    RULE_TEXT = "用力将我抛起来吧！"
    GRAVITY = 0.4
    FRICTION_X = 0.98
    TIME_STEP = 20
    PX_PER_METER = 100
    LAND_THRESHOLD = 3
    MIN_LAUNCH = -1  # 向上速度阈值（vy<0 向上，小于 -1 才触发飞行）

    # 落地分档：按最高高度（米）匹配回复
    LAND_TIERS = [
        (50,  ["嗯……是不是最近吃太多变重了……",
               "唔，训练员今天是不是没吃饱？"]),
        (200, ["比想象中高了一点！",
               "这个高度，勉强能热身吧"]),
        (350, ["好高！就像冲刺时飞起来的感觉",
               "训练员今天一定是吃饱了"]),
        (500, ["哇啊啊啊啊啊！",
               "训练员，刚才那下的速度是不是超过tama酱了"]),
        (float("inf"), ["刚才……是不是飞到云上面去了？",
                        "好晕……吃不下饭了……"]),
    ]

    def __init__(self, pet) -> None:
        self.pet = pet
        self._active = False
        self._after_id = None
        self._vel_x = 0
        self._vel_y = 0
        self._ground_y = 0
        self._height = 0
        self._max_height = 0
        self._in_air = False
        self._counter_win = None
        self._counter_label = None
        self._counter_anchor = None
        self._drag_off = None

    # ── 生命周期 ────────────────────────────
    def start(self):
        self._active = True
        # 地面 = 屏幕最底端，并先把桌宠放到屏幕底部
        self._ground_y = self.pet.screen_h - self.pet.pet_size[1]
        self.pet.y = self._ground_y
        self.pet._move()
        self.pet.label.unbind("<ButtonRelease-1>")
        self.pet.label.bind("<ButtonRelease-1>", self._game_drag_end)
        self.pet.show_talk(self.RULE_TEXT)
        self.pet.root.after(3000, self.pet.hide_talk)
        self._create_counter()

    def stop(self):
        self._active = False
        if self._after_id:
            self.pet.root.after_cancel(self._after_id)
            self._after_id = None
        self.pet.label.unbind("<ButtonRelease-1>")
        self.pet.label.bind("<ButtonRelease-1>", self.pet._on_drag_end)
        self._destroy_counter()
        self.pet.y = self._ground_y
        self.pet._move()
        self.pet._set_pet_image("stay")

    # ── 抛高 ────────────────────────────────
    def _game_drag_end(self, e):
        self.pet._cancel_click_timer()
        self.pet.is_dragging = False
        self._cancel_after()
        self.pet.stop_all_animations()

        vx = self.pet.velocity_x
        vy = self.pet.velocity_y
        # 只有向上抛（vy<0）且达到阈值才触发飞行；方向完全保留脱手速度
        if vy < self.MIN_LAUNCH:
            self._vel_x = vx
            self._vel_y = vy
            self._in_air = True
            self._height = 0
            self._max_height = 0
            self._update_counter(0)
            self._physics_loop()
        else:
            # 未触发飞行：回到正常桌宠交互
            self.pet._on_drag_end(e)

    def _physics_loop(self):
        if not self._active:
            return
        self._vel_y += self.GRAVITY
        self._vel_x *= self.FRICTION_X
        nx = self.pet.x + self._vel_x
        ny = self.pet.y + self._vel_y

        # 左右边界：不能掉出屏幕，撞边反弹
        left = 0
        right = self.pet.screen_w - self.pet.pet_size[0]
        if nx < left:
            nx = left
            self._vel_x = -self._vel_x * 0.4
        elif nx > right:
            nx = right
            self._vel_x = -self._vel_x * 0.4

        self.pet.x, self.pet.y = nx, ny
        self.pet._move()
        self.pet._set_pet_image("click")

        height = max(0, self._ground_y - self.pet.y)
        self._height = height
        if height > self._max_height:
            self._max_height = height
        self._update_counter(height)

        # 落回地面（接近地面且正在下落时直接吸附，避免抖动）
        if self.pet.y >= self._ground_y - self.LAND_THRESHOLD and self._vel_y > 0:
            self.pet.y = self._ground_y
            self.pet._move()
            self.pet._set_pet_image("stay")
            self._in_air = False
            self._update_counter(self._max_height)
            # 落地 0.5 秒后再给回复
            self.pet.root.after(500, lambda: self._landing_reply(self._max_height))
            return

        self._after_id = self.pet.root.after(self.TIME_STEP, self._physics_loop)

    def _cancel_after(self):
        if self._after_id:
            self.pet.root.after_cancel(self._after_id)
            self._after_id = None

    # ── 落地回复 ────────────────────────────
    @staticmethod
    def replies_for_height(height_px: float) -> list:
        """按飞行高度（像素）返回对应档位的台词候选列表。"""
        meters = height_px / FlyHighGame.PX_PER_METER
        for limit, rlist in FlyHighGame.LAND_TIERS:
            if meters < limit:
                return rlist
        return FlyHighGame.LAND_TIERS[-1][1]

    def _landing_reply(self, height_px):
        import random
        replies = self.replies_for_height(height_px)
        text = random.choice(replies)
        # 优先抢占气泡：取消待执行的自动隐藏，再显示落地回复
        if hasattr(self.pet, '_hide_timer') and self.pet._hide_timer:
            self.pet.root.after_cancel(self.pet._hide_timer)
            self.pet._hide_timer = None
        self.pet.show_talk(text)
        self.pet._hide_timer = self.pet.root.after(4000, self.pet.hide_talk)

    # ── 计数器 ──────────────────────────────
    def _create_counter(self):
        if self._counter_win:
            return
        self._counter_anchor = (self.pet.x, max(30, self._ground_y - 80))
        self._counter_win = tk.Toplevel(self.pet.root)
        self._counter_win.overrideredirect(True)
        self._counter_win.attributes("-topmost", True)
        self._counter_win.configure(bg=cfg.C_BG)
        panel = tk.Frame(self._counter_win, bg=cfg.C_BG,
                         highlightbackground=cfg.C_ROSE_DEEP, highlightthickness=2)
        panel.pack(padx=4, pady=4)
        self._counter_label = tk.Label(
            panel,
            text="0.0 米",
            font=("Microsoft YaHei", 18, "bold"),
            bg=cfg.C_BG, fg=cfg.C_ROSE_DEEP,
        )
        self._counter_label.pack(padx=10, pady=2)
        sub = tk.Label(panel, text="▲ 飞行高度",
                       font=("Microsoft YaHei", 9),
                       bg=cfg.C_BG, fg=cfg.C_ASH_DARK)
        sub.pack()
        # 支持拖动计数器
        for w in (panel, self._counter_label, sub):
            w.bind("<ButtonPress-1>", self._counter_press)
            w.bind("<B1-Motion>", self._counter_drag)
        ax, ay = self._counter_anchor
        self._counter_win.geometry(f"+{int(ax)}+{int(ay)}")

    def _counter_press(self, e):
        self._drag_off = (e.x_root - self._counter_win.winfo_x(),
                          e.y_root - self._counter_win.winfo_y())

    def _counter_drag(self, e):
        if self._drag_off:
            nx = e.x_root - self._drag_off[0]
            ny = e.y_root - self._drag_off[1]
            self._counter_win.geometry(f"+{int(nx)}+{int(ny)}")

    def _update_counter(self, value):
        if self._counter_win and self._counter_label:
            meters = value / self.PX_PER_METER
            self._counter_label.config(text=f"{meters:.1f} 米")

    def _destroy_counter(self):
        if self._counter_win:
            self._counter_win.destroy()
            self._counter_win = None
            self._counter_label = None
