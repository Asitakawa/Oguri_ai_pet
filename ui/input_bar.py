"""聊天输入条"""
import threading
import tkinter as tk
from core import config as cfg


class InputBar:
    def __init__(self, pet):
        self.pet = pet
        self.window = None
        self.entry = None

    def show(self):
        p = self.pet
        if self.window:
            self.window.deiconify()
            self.entry.focus()
            return
        self.window = tk.Toplevel(p.root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.config(bg="black")
        self.window.attributes("-transparentcolor", "black")

        bw, bh = cfg.INPUT_BOX_WIDTH, cfg.INPUT_BOX_HEIGHT
        canvas = tk.Canvas(self.window, width=bw, height=bh,
                           bg="black", highlightthickness=0)
        canvas.pack()
        canvas.create_rounded_rectangle(3, 3, bw - 3, bh - 3, radius=18,
                                        fill=cfg.C_INPUT_BG,
                                        outline=cfg.C_BUBBLE_OUTLINE, width=1)

        self.entry = tk.Entry(
            canvas, font=(cfg.FONT_FAMILY, cfg.FONT_SIZE), bg=cfg.C_INPUT_BG,
            fg=cfg.C_TEXT, relief="flat", bd=0, insertbackground=cfg.C_ACCENT,
            highlightthickness=0, insertwidth=2,
        )
        self.entry.place(x=14, y=10, width=220, height=34)
        self.entry.bind("<Return>", lambda e: self._send())
        self.entry.bind("<Control-s>", lambda e: self._send(with_screenshot=True))
        self.entry.focus()

        y_mid = 9
        h_btn = 36
        tk.Button(canvas, text="发送", font=(cfg.FONT_FAMILY, 10, 'bold'),
                  bg=cfg.C_BTN_PRIMARY, fg="white", relief="flat", bd=0,
                  activebackground=cfg.C_BTN_PRIMARY_HOVER, cursor="hand2",
                  command=self._send).place(x=242, y=y_mid, width=50, height=h_btn)
        tk.Button(canvas, text="📸", font=(cfg.FONT_FAMILY, 12),
                  bg=cfg.C_SKY_DEEP, fg="white", relief="flat", bd=0,
                  activebackground=cfg.C_SKY, cursor="hand2",
                  command=lambda: self._send(with_screenshot=True)).place(x=296, y=y_mid, width=38, height=h_btn)
        tk.Button(canvas, text="✕", font=(cfg.FONT_FAMILY, 12, 'bold'),
                  bg=cfg.C_ROSE, fg="white", relief="flat", bd=0, cursor="hand2",
                  activebackground=cfg.C_ROSE_DEEP,
                  command=lambda: self.window.withdraw()).place(x=338, y=y_mid, width=38, height=h_btn)

        self._update_pos()

    def _update_pos(self):
        p = self.pet
        if not self.window or self.window.state() == "withdrawn":
            return
        ix = max(10, min(p.x + (p.pet_size[0] - 380) // 2, p.screen_w - 380 - 10))
        iy = max(10, min(p.y + p.pet_size[1] + 6, p.screen_h - 56 - 10))
        self.window.geometry(f"380x56+{int(ix)}+{int(iy)}")
        if self.window.state() != "withdrawn":
            p.root.after(30, self._update_pos)

    def _send(self, with_screenshot=False):
        p = self.pet
        msg = self.entry.get().strip()
        if not msg and not with_screenshot:
            p.show_talk(cfg.INPUT_EMPTY)
            p.root.after(2000, p.hide_talk)
            return
        self.entry.delete(0, tk.END)
        loading = cfg.INPUT_SCREENSHOT_THINKING if with_screenshot else (cfg.INPUT_THINKING if msg else cfg.SCREENSHOT_LOADING)
        p.show_talk(loading)
        threading.Thread(target=p._process_ai_response, args=(msg, with_screenshot), daemon=True).start()
