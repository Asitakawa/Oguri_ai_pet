"""悬浮进度条"""
import tkinter as tk

from core import config as cfg


class StatusBar:
    def __init__(self, pet):
        self.pet = pet
        self.visible = False
        self.win = tk.Toplevel(pet.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", "black")
        self.win.config(bg="black")
        cw, ch = cfg.STATUS_BAR_WIDTH, cfg.STATUS_BAR_HEIGHT
        self.canvas = tk.Canvas(self.win, width=cw, height=ch,
                                 bg="black", highlightthickness=0)
        self.canvas.pack()
        self.win.withdraw()

    def show(self):
        self.visible = True
        self._render()
        self.win.deiconify()

    def hide(self):
        self.visible = False
        self.win.withdraw()

    def _position(self):
        cx = self.pet.x + (self.pet.pet_size[0] - cfg.STATUS_BAR_WIDTH) // 2
        cy = self.pet.y + self.pet.pet_size[1] + 4
        self.win.geometry(f"+{int(cx)}+{int(cy)}")

    def _render(self):
        self.canvas.delete("all")
        w, h = cfg.STATUS_BAR_WIDTH, cfg.STATUS_BAR_HEIGHT
        m = 6
        bh = 10
        gp = 4
        hp = self.pet.status.hunger_pct / 100
        ep = self.pet.status.energy_pct / 100

        self.canvas.create_rounded_rectangle(2, 2, w - 2, h - 2, radius=8,
            fill=cfg.C_BG, outline=cfg.C_ASH_LIGHT, width=1)
        fs = max(8, cfg.FONT_SIZE - 2)

        y1 = m
        self.canvas.create_rectangle(m, y1, w - m, y1 + bh, fill=cfg.C_ASH_LIGHT, outline="")
        self.canvas.create_rectangle(m, y1, m + (w - 2 * m) * hp, y1 + bh, fill=cfg.C_ROSE, outline="")
        self.canvas.create_text(m + 2, y1 + bh // 2, anchor="w",
            text=f"🍙 {int(self.pet.status.hunger_pct)}%",
            font=(cfg.FONT_FAMILY, fs), fill=cfg.C_WOOD)

        y2 = y1 + bh + gp
        self.canvas.create_rectangle(m, y2, w - m, y2 + bh, fill=cfg.C_ASH_LIGHT, outline="")
        self.canvas.create_rectangle(m, y2, m + (w - 2 * m) * ep, y2 + bh, fill=cfg.C_SKY, outline="")
        self.canvas.create_text(m + 2, y2 + bh // 2, anchor="w",
            text=f"⚡ {int(self.pet.status.energy_pct)}%",
            font=(cfg.FONT_FAMILY, fs), fill=cfg.C_WOOD)

        self._position()
