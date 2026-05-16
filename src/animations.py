"""
动画系统 Mixin
提供摇晃、弹跳、惯性、吃东西、打盹、歪头等动画
"""
import math
from . import config as cfg


class AnimationMixin:

    def stop_all_animations(self):
        self.shake_animation = False
        self.bounce_animation = False
        self.inertia_active = False

    # ========== 惯性 ==========
    def apply_inertia(self):
        if not self.inertia_active or self.is_dragging:
            return
        self.velocity_x *= cfg.INERTIA_FRICTION
        self.velocity_y *= cfg.INERTIA_FRICTION
        new_x = max(0, min(self.x + self.velocity_x, self.screen_w - self.pet_size[0]))
        new_y = max(0, min(self.y + self.velocity_y, self.screen_h - self.pet_size[1]))
        self.x, self.y = new_x, new_y
        self._move()
        if abs(self.velocity_x) > 0.3 or abs(self.velocity_y) > 0.3:
            self.root.after(max(15, int(30 / (abs(self.velocity_x) + abs(self.velocity_y) + 1))),
                           self.apply_inertia)
        else:
            self.inertia_active = False

    # ========== 摇晃 ==========
    def start_shake_animation(self):
        if self.shake_animation:
            return
        self.shake_animation = True
        self._ori_x = self.x
        self._sf = 0
        self._do_shake()

    def _do_shake(self):
        if not self.shake_animation:
            return
        self.x = self._ori_x + math.sin(self._sf * 0.5) * self.shake_intensity
        self._move()
        self._sf += 1
        if self._sf < 20:
            self.root.after(30, self._do_shake)
        else:
            self.shake_animation = False
            self.x = self._ori_x
            self._move()

    # ========== 弹跳 ==========
    def start_bounce_animation(self):
        if self.bounce_animation:
            return
        self.bounce_animation = True
        self._ori_y = self.y
        self._bf = 0
        self._do_bounce()

    def _do_bounce(self):
        if not self.bounce_animation:
            return
        p = self._bf / 15.0
        h = self.bounce_height * (1 - (2 * p - 1) ** 2) if p <= 1 else 0
        self.y = self._ori_y - h
        self._move()
        self._bf += 1
        if self._bf < 30:
            self.root.after(25, self._do_bounce)
        else:
            self.bounce_animation = False
            self.y = self._ori_y
            self._move()

    def _move(self):
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")
        self.bubble.update_position()
        if hasattr(self, 'status_bar') and self.status_bar and self.status_bar.visible:
            self.status_bar._position()

    # ========== 小动作 ==========
    def eat_action(self, callback=None):
        self.stop_all_animations()
        x0, y0 = self.x, self.y
        a = int(5 * (1 + self.scale_factor))

        def frame(step):
            if step >= 18:
                self.x, self.y = x0, y0
                self._move()
                if callback:
                    callback()
                return
            p = step / 18.0
            dx = a * 0.6 * math.sin(p * math.pi * 4) * (1 - p)
            dy = -a * 1.2 * abs(math.sin(p * math.pi * 3)) * (1 - p * 0.5)
            self.x, self.y = x0 + dx, y0 + dy
            self._move()
            self.root.after(55, lambda s=step: frame(s + 1))

        frame(0)

    def nap_action(self, duration=2.0, callback=None):
        self.stop_all_animations()
        x0, y0 = self.x, self.y
        w0, h0 = self.pet_size

        def shrink(step):
            if step >= 8:
                self.root.after(int(duration * 1000), lambda: expand(0))
                return
            p = step / 8.0
            s = 1 - p * 0.15
            self.root.geometry(f"{int(w0 * s)}x{int(h0 * s)}+{int(x0 + w0 * (1 - s) / 2)}+{int(y0 + h0 * (1 - s))}")
            self.bubble.update_position()
            self.root.after(40, lambda s=step: shrink(s + 1))

        def expand(step):
            if step >= 8:
                self.root.geometry(f"{w0}x{h0}+{int(x0)}+{int(y0)}")
                self.bubble.update_position(force=True)
                self.x, self.y = x0, y0
                if callback:
                    callback()
                return
            p = step / 8.0
            s = 0.85 + p * 0.15
            self.root.geometry(f"{int(w0 * s)}x{int(h0 * s)}+{int(x0 + w0 * (1 - s) / 2)}+{int(y0 + h0 * (1 - s))}")
            self.bubble.update_position()
            self.root.after(40, lambda s=step: expand(s + 1))

        shrink(0)

    def tilt_head(self, callback=None):
        self.stop_all_animations()
        x0 = self.x
        a = int(6 * (1 + self.scale_factor))

        def tilt(step):
            if step >= 24:
                self.x = x0
                self._move()
                if callback:
                    callback()
                return
            p = step / 24.0
            dx = a * math.sin(p * math.pi * 2.5) * (1 - p * 0.6)
            self.x = x0 + dx
            self._move()
            self.root.after(50, lambda s=step: tilt(s + 1))

        tilt(0)
