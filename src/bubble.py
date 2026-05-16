"""
对话气泡组件 - 带三角尾巴的漫画式气泡
"""
import tkinter as tk
from .config import BUBBLE_BASE_WIDTH, BUBBLE_BASE_HEIGHT
from .config import C_BUBBLE_BG, C_BUBBLE_OUTLINE, C_BUBBLE_TEXT


class ChatBubble:

    def __init__(self, pet):
        self.pet = pet
        self.window = None
        self.canvas = None
        self.label = None
        self._offset_x = 0
        self._offset_y = 0
        self._create()

    def _create(self):
        bw, bh = BUBBLE_BASE_WIDTH + 20, BUBBLE_BASE_HEIGHT + 16
        bubble = tk.Toplevel(self.pet.root)
        bubble.overrideredirect(True)
        bubble.attributes('-topmost', True)
        bubble.attributes('-transparentcolor', 'black')
        bubble.config(bg='black')
        bubble.withdraw()

        canvas = tk.Canvas(bubble, bg='black', highlightthickness=0,
                           width=bw, height=bh)
        canvas.pack()
        label = tk.Label(canvas, text="", font=("微软雅黑", 11, "bold"),
                         fg=C_BUBBLE_TEXT, bg=C_BUBBLE_BG, wraplength=210,
                         justify='left')

        self.window = bubble
        self.canvas = canvas
        self.label = label
        self._bw = bw
        self._bh = bh

    def recalc_offsets(self):
        pet_size = self.pet.pet_size
        hs = max(-24, int(pet_size[0] * 0.02))
        self._offset_x = -(BUBBLE_BASE_WIDTH + hs + 20)
        self._offset_y = max(5, int(pet_size[1] * 0.10))

    def update_position(self, force=False):
        if not self.window:
            return
        if not force and self.window.state() != "normal":
            return
        tx = self.pet.x + self._offset_x
        ty = self.pet.y + self._offset_y
        sw, sh = self.pet.screen_w, self.pet.screen_h
        bx = max(0, min(int(tx), sw - self._bw))
        by = max(0, min(int(ty), sh - self._bh))
        self.window.geometry(f"{self._bw}x{self._bh}+{bx}+{by}")

    def show(self, text):
        if hasattr(self.pet, '_set_pet_image'):
            self.pet._set_pet_image("talk")
        else:
            self.pet.label.config(image=self.pet.images.get("talk", self.pet.current_img))
        self.label.config(text=text)
        c = self.canvas
        c.delete("all")
        bw, bh = self._bw, self._bh
        pad, r = 8, 18
        x1, y1 = pad, pad
        x2, y2 = bw - pad - 8, bh - pad

        # 阴影
        c.create_rounded_rectangle(x1 + 2, y1 + 2, x2 + 2, y2 + 2,
                                   radius=r, fill="#e8e4de", outline="")
        # 主体
        c.create_rounded_rectangle(x1, y1, x2, y2,
                                   radius=r, fill=C_BUBBLE_BG,
                                   outline=C_BUBBLE_OUTLINE, width=1)
        # 三角尾巴
        tx = bw - 10
        ty = y1 + r + 8
        c.create_polygon(tx, ty - 7, bw - 2, ty, tx, ty + 7,
                        fill=C_BUBBLE_BG, outline=C_BUBBLE_OUTLINE, width=1)
        # 尾巴内三角（覆盖线条）
        c.create_polygon(tx + 1, ty - 5, bw - 3, ty, tx + 1, ty + 5,
                        fill=C_BUBBLE_BG, outline="")

        self.label.place(x=20, y=22)
        self.update_position(force=True)
        self.window.deiconify()

    def hide(self):
        if self.pet and not self.pet.is_auto_talking:
            if hasattr(self.pet, '_set_pet_image'):
                self.pet._set_pet_image("stay")
            else:
                self.pet.label.config(image=self.pet.current_img)
        if self.window:
            self.window.withdraw()

    @property
    def visible(self):
        return self.window and self.window.state() == "normal"
