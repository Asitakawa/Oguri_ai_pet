"""
悬浮状态条：显示饱腹度和活力值双色进度条，实时跟随角色
"""
import tkinter as tk
from . import config as cfg


class StatusBar:

    def __init__(self, pet):
        self.pet = pet
        self.window = None
        self.canvas = None
        self._refresh_timer = None
        self._create()

    def _create(self):
        w = tk.Toplevel(self.pet.root)
        w.overrideredirect(True)
        w.attributes('-topmost', True)
        w.attributes('-transparentcolor', 'black')
        w.config(bg='black')
        w.withdraw()

        canvas = tk.Canvas(w, bg='black', highlightthickness=0,
                          width=cfg.STATUS_BAR_WIDTH, height=cfg.STATUS_BAR_HEIGHT)
        canvas.pack()
        self.window = w
        self.canvas = canvas

    def show(self):
        self._draw()
        self._position()
        self.window.deiconify()
        self._start_refresh()

    def hide(self):
        self._stop_refresh()
        if self.window:
            self.window.withdraw()

    def _start_refresh(self):
        self._stop_refresh()
        self._refresh_loop()

    def _refresh_loop(self):
        if not self.visible:
            return
        self._draw()
        self._position()
        self._refresh_timer = self.pet.root.after(800, self._refresh_loop)

    def _stop_refresh(self):
        if self._refresh_timer:
            self.pet.root.after_cancel(self._refresh_timer)
            self._refresh_timer = None

    def _draw(self):
        c = self.canvas
        c.delete("all")
        w, h = cfg.STATUS_BAR_WIDTH, cfg.STATUS_BAR_HEIGHT
        bar_w = w - 60
        bar_h = 10
        bar_x = 55

        c.create_rounded_rectangle(2, 2, w - 2, h - 2, radius=10,
                                   fill=cfg.C_PANEL_BG, outline=cfg.C_ASH_LIGHT, width=1)

        c.create_text(28, 12, text="🍙", font=("微软雅黑", 10),
                      fill=cfg.C_WOOD, anchor="center")

        hp = self.pet.status.hunger_pct
        h_color = cfg.C_MINT if hp > 30 else cfg.C_ROSE
        c.create_rectangle(bar_x, 4, bar_x + int(bar_w * hp / 100), 4 + bar_h,
                          fill=h_color, outline="")
        c.create_rectangle(bar_x, 4, bar_x + bar_w, 4 + bar_h,
                          fill="", outline=cfg.C_ASH_LIGHT, width=1)
        c.create_text(bar_x + bar_w + 16, 9, text=f"{hp}%",
                      font=("微软雅黑", 9), fill=cfg.C_WOOD, anchor="w")

        c.create_text(28, 26, text="⚡", font=("微软雅黑", 10),
                      fill=cfg.C_WOOD, anchor="center")

        ep = self.pet.status.energy_pct
        e_color = cfg.C_SKY if ep > 25 else cfg.C_ROSE_DEEP
        c.create_rectangle(bar_x, 18, bar_x + int(bar_w * ep / 100), 18 + bar_h,
                          fill=e_color, outline="")
        c.create_rectangle(bar_x, 18, bar_x + bar_w, 18 + bar_h,
                          fill="", outline=cfg.C_ASH_LIGHT, width=1)
        c.create_text(bar_x + bar_w + 16, 23, text=f"{ep}%",
                      font=("微软雅黑", 9), fill=cfg.C_WOOD, anchor="w")

    def _position(self):
        sx = max(10, min(int(self.pet.x + (self.pet.pet_size[0] - cfg.STATUS_BAR_WIDTH) // 2),
                        self.pet.screen_w - cfg.STATUS_BAR_WIDTH - 10))
        sy = max(10, int(self.pet.y - cfg.STATUS_BAR_HEIGHT - 10))
        self.window.geometry(f"{cfg.STATUS_BAR_WIDTH}x{cfg.STATUS_BAR_HEIGHT}+{sx}+{sy}")

    @property
    def visible(self):
        return self.window and self.window.state() == "normal"
