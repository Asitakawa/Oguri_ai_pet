"""小游戏：一飞冲天 — 仿古早 QQ 宠物抛高游戏

继承 BaseGame 以获得统一的生命周期、清理与计数器管理。
与其他游戏的差别：
- 唯一靠「左键拖拽 + 松手上抛」操作的游戏，因此保留这三个交互（见 _PASSTHROUGH_BINDINGS）
- 不设胜负，也不会自行结束：由玩家用右键菜单「⏹ 退出游戏」或 Esc 退出
"""
from __future__ import annotations

import random
import tkinter as tk

from core import config as cfg
from game.base import BaseGame


class FlyHighGame(BaseGame):
    NAME = "一飞冲天"
    DESCRIPTION = "用力把我抛起来吧！看看能飞多高"
    RULE_TEXT = "用力将我抛起来吧！"
    FRAME_MS = 20

    # 抛高靠拖拽 + 松手测速，这三个交互必须留给本游戏
    _PASSTHROUGH_BINDINGS = frozenset({
        "<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>",
    })

    GRAVITY = 0.4
    FRICTION_X = 0.98
    LAND_THRESHOLD = 3
    MIN_LAUNCH = -1  # 向上速度阈值（vy<0 向上，小于 -1 才触发飞行）
    LAND_REPLY_DELAY_MS = 500

    # 高度换算。100 px/m 意味着屏幕只有 1080px 时上限约 10 米，
    # LAND_TIERS 的后几档永远够不到；10 px/m 与其他游戏（DashRules）一致，
    # 让 50–500 米的档位落在真实可达范围内。
    PX_PER_METER = 10.0

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
        super().__init__(pet)
        self._vel_x = 0.0
        self._vel_y = 0.0
        self._ground_y = 0.0
        self._max_height = 0.0
        self._physics_id = None

    # ── 生命周期 ────────────────────────────
    def start(self) -> None:
        # 先让基类快照当前位置/表情，再把自己挪到屏幕底部；顺序反了的话
        # _restore_pet 会把「屏幕底部」当成原始位置，退出后桌宠回不到原处
        super().start()
        self._ground_y = self.pet.screen_h - self.pet.pet_size[1]
        self.pet.x = max(0, min(self.pet.x, self.pet.screen_w - self.pet.pet_size[0]))
        self.pet.y = self._ground_y
        self.pet._move()
        self._bind(self.pet.label, "<ButtonRelease-1>", self._on_throw)

    def stop(self) -> None:
        self._cancel_physics()
        # 解绑本游戏接管的松手处理
        try:
            self.pet.label.unbind("<ButtonRelease-1>")
        except Exception:
            pass
        super().stop()
        # BaseGame._restore_pet 会把桌宠放回开始前的位置与表情，
        # 抛高期间被显式挪到屏幕底部，这里不再覆盖它

    def _cancel_physics(self) -> None:
        if self._physics_id is not None:
            self._cancel_after(self._physics_id)
            self._physics_id = None

    # ── 计数器 ──────────────────────────────
    def _build_counter(self, panel: tk.Frame) -> None:
        self._counter_label = tk.Label(
            panel, text="0.0 米", font=(cfg.FONT_FAMILY, 18, "bold"),
            bg=cfg.C_BG, fg=cfg.C_ROSE_DEEP,
        )
        self._counter_label.pack(padx=10, pady=2)
        tk.Label(panel, text="▲ 飞行高度", font=(cfg.FONT_FAMILY, 9),
                 bg=cfg.C_BG, fg=cfg.C_ASH_DARK).pack()

    def _update_counter(self, value: float) -> None:
        if self._counter_label:
            self._counter_label.config(text=f"{value / self.PX_PER_METER:.1f} 米")

    # ── 抛高 ────────────────────────────────
    def _on_throw(self, event=None) -> None:
        self.pet._cancel_click_timer()
        self.pet.is_dragging = False
        self.pet.stop_all_animations()

        vx, vy = self._release_velocity()
        # 只有向上抛（vy<0）且达到阈值才触发飞行；方向完全保留脱手速度
        if vy < self.MIN_LAUNCH:
            self._vel_x = vx
            self._vel_y = vy
            self._max_height = 0.0
            self._update_counter(0)
            self._cancel_physics()
            self._physics_tick()
        else:
            # 未触发飞行：回到正常桌宠交互
            self.pet._on_drag_end(event)

    def _release_velocity(self):
        """把桌宠记录的脱手速度换算成「每物理帧位移」。

        桌宠的 velocity_x/velocity_y 是**每鼠标事件**的位移（见
        ui/pet_window._on_drag_move 对最近 3 次事件的滑动平均），单位是
        px/事件。直接当 px/帧用会让手感随鼠标轮询率变化——高回报率鼠标
        每帧内产生的事件更多，同样的甩动会飞出完全不同的高度。

        这里按事件的时间间隔把它归一化成 px/s，再乘物理步长换算回 px/帧。
        """
        vx_ev = self.pet.velocity_x
        vy_ev = self.pet.velocity_y
        dt = self._event_dt_seconds()
        if dt <= 0:
            return vx_ev, vy_ev
        step_s = self.FRAME_MS / 1000.0
        return vx_ev / dt * step_s, vy_ev / dt * step_s

    def _event_dt_seconds(self) -> float:
        """相邻鼠标事件的平均间隔（秒）；拿不到时回退到一帧时长。"""
        stamps = getattr(self.pet, "_drag_event_times", None)
        if not stamps or len(stamps) < 2:
            return self.FRAME_MS / 1000.0
        span = stamps[-1] - stamps[0]
        if span <= 0:
            return self.FRAME_MS / 1000.0
        return span / (len(stamps) - 1)

    def _physics_tick(self) -> None:
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

        height = max(0.0, self._ground_y - self.pet.y)
        if height > self._max_height:
            self._max_height = height
        self._update_counter(height)

        # 落回地面（接近地面且正在下落时直接吸附，避免抖动）
        if self.pet.y >= self._ground_y - self.LAND_THRESHOLD and self._vel_y > 0:
            self.pet.y = self._ground_y
            self.pet._move()
            self.pet._set_pet_image("stay")
            self._update_counter(self._max_height)
            # 落地 0.5 秒后再给回复；用基类调度，退出游戏时会被一起取消，
            # 不会把上一局的台词漏到下一局
            self._schedule(self.LAND_REPLY_DELAY_MS,
                           lambda: self._landing_reply(self._max_height))
            self._physics_id = None
            return

        self._physics_id = self._schedule(self.FRAME_MS, self._physics_tick)

    # ── 落地回复 ────────────────────────────
    @staticmethod
    def replies_for_height(height_px: float) -> list:
        """按飞行高度（像素）返回对应档位的台词候选列表。"""
        meters = height_px / FlyHighGame.PX_PER_METER
        for limit, rlist in FlyHighGame.LAND_TIERS:
            if meters < limit:
                return rlist
        return FlyHighGame.LAND_TIERS[-1][1]

    def _landing_reply(self, height_px: float) -> None:
        # 刷新飞行纪录（最高点，米）
        companion = getattr(self.pet, "companion", None)
        if companion is not None:
            try:
                companion.record_max("max_fly_meters", height_px / self.PX_PER_METER)
            except Exception:
                pass
        text = random.choice(self.replies_for_height(height_px))
        # 优先抢占气泡：取消待执行的自动隐藏，再显示落地回复
        if getattr(self.pet, "_hide_timer", None):
            self.pet.root.after_cancel(self.pet._hide_timer)
            self.pet._hide_timer = None
        self.pet.show_talk(text)
        self.pet._hide_timer = self.pet.root.after(4000, self.pet.hide_talk)
