"""漫画对话气泡"""
import tkinter as tk
from core import config as cfg
from utils.tk_ext import _create_rounded_rectangle


class ChatBubble:
    def __init__(self, pet):
        self.pet = pet
        self.win = tk.Toplevel(pet.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", "black")
        self.win.config(bg="black")
        self.canvas = tk.Canvas(
            self.win, width=cfg.BUBBLE_BASE_WIDTH, height=cfg.BUBBLE_BASE_HEIGHT,
            bg="black", highlightthickness=0,
        )
        self.canvas.pack()
        self._text_id = None
        self._rect_id = None
        self.hide()

    def recalc_offsets(self):
        self.bw = int(cfg.BUBBLE_BASE_WIDTH * self.pet.scale_factor)
        self.bh = int(cfg.BUBBLE_BASE_HEIGHT * self.pet.scale_factor)

    def update_position(self, force=False):
        px, py = self.pet.x, self.pet.y
        pw, ph = self.pet.pet_size
        bx = px + (pw - self.bw) // 2
        by = py - self.bh - 10
        self.win.geometry(f"{self.bw}x{self.bh}+{int(bx)}+{int(by)}")

    def show(self, text):
        self.recalc_offsets()
        margin = 12
        self.canvas.delete("all")
        self.canvas.config(width=self.bw, height=self.bh)
        r = 14
        self._rect_id = self.canvas.create_rounded_rectangle(
            2, 2, self.bw - 2, self.bh - 2, radius=r,
            fill=cfg.C_BUBBLE_BG, outline=cfg.C_BUBBLE_OUTLINE, width=1,
        )
        self._text_id = self.canvas.create_text(
            self.bw // 2, self.bh // 2 - 4,
            text=text, font=(cfg.FONT_FAMILY, cfg.FONT_SIZE),
            fill=cfg.C_BUBBLE_TEXT, width=self.bw - margin * 2,
            justify="center", anchor='center',
        )
        self.update_position(force=True)
        self.win.deiconify()
        self.win.lift()

    def hide(self):
        self.win.withdraw()
