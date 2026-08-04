"""小游戏公共基类 — 统一生命周期、事件、计数器与气泡管理"""
from __future__ import annotations

import time
import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

from core import config as cfg
from utils.logger import get_logger

log = get_logger("game.base")


class BaseGame:
    """所有小游戏的基类。

    约定：
    - 子类在 start() 中先调用 super().start()，再绑定自己的事件；
    - stop() 自动清理 after 回调、事件绑定、计数器窗口并恢复桌宠（幂等）；
    - _finish() 在清理后播报结算台词，并让游戏管理器解除占用。
    """

    NAME = "未命名游戏"
    DESCRIPTION = ""
    RULE_TEXT = "开始了！"
    FRAME_MS = 33  # 默认帧间隔

    # 游戏期间禁用的桌宠交互，结束时恢复
    _PET_BINDINGS: Dict[str, str] = {
        "<ButtonPress-1>": "_on_drag_start",
        "<B1-Motion>": "_on_drag_move",
        "<ButtonRelease-1>": "_on_drag_end",
        "<Double-Button-1>": "_on_double_click",
        "<Button-2>": "_on_middle_click",
        "<Enter>": "_on_enter",
        "<Leave>": "_on_leave",
    }

    def __init__(self, pet) -> None:
        self.pet = pet
        self._active = False
        self._after_ids = set()
        self._bindings: List[Tuple[object, str, Callable]] = []
        self._pet_originals: Dict[str, Callable] = {}
        self._saved_pos: Optional[Tuple[float, float]] = None
        self._saved_img: Optional[str] = None
        self._counter_win: Optional[tk.Toplevel] = None
        self._counter_label: Optional[tk.Label] = None
        self._counter_anchor: Optional[Tuple[int, int]] = None
        self._counter_drag_off = None
        self._last_talk = 0.0

    # ── 生命周期 ──────────────────────────
    def start(self) -> None:
        self._active = True
        self._saved_pos = (self.pet.x, self.pet.y)
        self._saved_img = getattr(self.pet, "_cur_img_key", None)
        self._disable_pet_interactions()
        self._create_counter()
        self._talk(self.RULE_TEXT, 3000)
        self._bind_all("<KeyPress-Escape>", self._exit_game)

    def stop(self) -> None:
        self._active = False
        self._cancel_all_after()
        self._unbind_all()
        self._destroy_counter()
        self._restore_pet_interactions()
        self._restore_pet()

    def is_active(self) -> bool:
        return self._active

    # ── 桌宠交互禁用/恢复 ──────────────────
    def _disable_pet_interactions(self) -> None:
        self._pet_originals = {}
        if not self.pet.label:
            return
        for seq, attr in self._PET_BINDINGS.items():
            func = getattr(self.pet, attr, None)
            if func:
                self._pet_originals[seq] = func
        for seq in self._pet_originals:
            try:
                self.pet.label.bind(seq, self._noop)
            except Exception as e:
                log.debug("禁用交互失败 %s: %s", seq, e)

    def _restore_pet_interactions(self) -> None:
        for seq, func in self._pet_originals.items():
            try:
                self.pet.label.bind(seq, func)
            except Exception as e:
                log.debug("恢复交互失败 %s: %s", seq, e)
        self._pet_originals = {}

    @staticmethod
    def _noop(event=None):
        return None

    # ── 调度（stop 统一取消） ───────────────
    def _schedule(self, delay_ms: int, func: Callable, *args) -> str:
        after_id = self.pet.root.after(delay_ms, func, *args)
        self._after_ids.add(after_id)
        return after_id

    def _cancel_after(self, after_id: str) -> None:
        if after_id in self._after_ids:
            try:
                self.pet.root.after_cancel(after_id)
            except Exception:
                pass
            self._after_ids.discard(after_id)

    def _cancel_all_after(self) -> None:
        for aid in list(self._after_ids):
            try:
                self.pet.root.after_cancel(aid)
            except Exception as e:
                log.debug("取消 after 失败 %s: %s", aid, e)
        self._after_ids.clear()

    # ── 事件绑定（stop 统一解绑） ────────────
    def _bind(self, widget: object, sequence: str, func: Callable) -> None:
        try:
            widget.bind(sequence, func)
            self._bindings.append((widget, sequence, func))
        except Exception as e:
            log.debug("绑定失败 %s: %s", sequence, e)

    def _bind_all(self, sequence: str, func: Callable) -> None:
        self.pet.root.bind_all(sequence, func)
        self._bindings.append(("__all__", sequence, func))

    def _unbind_all(self) -> None:
        for widget, seq, _func in self._bindings:
            try:
                if widget == "__all__":
                    self.pet.root.unbind_all(seq)
                else:
                    widget.unbind(seq)
            except Exception as e:
                log.debug("解绑失败 %s: %s", seq, e)
        self._bindings.clear()

    # ── 气泡 ────────────────────────────────
    def _talk(self, text: str, duration: int = 4000) -> None:
        self.pet.show_talk(text)
        self._schedule(duration, self.pet.hide_talk)

    def _maybe_talk(self, text: str, duration: int = 1500,
                    min_interval: float = 0.8) -> None:
        """带冷却的气泡播报，避免高频刷新刷屏。"""
        now = time.time()
        if now - self._last_talk >= min_interval:
            self._last_talk = now
            self._talk(text, duration)

    def _exit_game(self, event=None) -> None:
        gm = getattr(self.pet, "game_manager", None)
        if gm is not None and getattr(gm, "_active", None) is self:
            gm.stop()

    @staticmethod
    def _make_click_through(win: tk.Toplevel) -> None:
        """让窗口对鼠标事件穿透（仅 Windows；失败时静默降级）。"""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            win.update_idletasks()
            hwnd = win.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT)
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0004 | 0x0020)  # NOMOVE|NOSIZE|NOZORDER|FRAMECHANGED
        except Exception as e:
            log.debug("设置点击穿透失败: %s", e)

    # ── 计数器窗口（可拖动） ────────────────
    def _create_counter(self) -> None:
        if self._counter_win:
            return
        self._counter_anchor = self._counter_anchor or (
            int(self.pet.x), max(30, int(self.pet.y) - 90))
        win = tk.Toplevel(self.pet.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=cfg.C_BG)
        panel = tk.Frame(win, bg=cfg.C_BG,
                         highlightbackground=cfg.C_ROSE_DEEP, highlightthickness=2)
        panel.pack(padx=4, pady=4)
        self._build_counter(panel)
        self._counter_win = win

        def _press(e):
            self._counter_drag_off = (
                e.x_root - win.winfo_x(), e.y_root - win.winfo_y())

        def _motion(e):
            if self._counter_drag_off:
                nx = e.x_root - self._counter_drag_off[0]
                ny = e.y_root - self._counter_drag_off[1]
                win.geometry(f"+{int(nx)}+{int(ny)}")

        for w in [panel] + list(panel.winfo_children()):
            w.bind("<ButtonPress-1>", _press)
            w.bind("<B1-Motion>", _motion)
        ax, ay = self._counter_anchor
        win.geometry(f"+{int(ax)}+{int(ay)}")

    def _build_counter(self, panel: tk.Frame) -> None:
        """子类可覆盖，向 panel 中添加自己的控件。"""
        self._counter_label = tk.Label(
            panel, text="", font=(cfg.FONT_FAMILY, 16, "bold"),
            bg=cfg.C_BG, fg=cfg.C_ROSE_DEEP)
        self._counter_label.pack(padx=10, pady=4)

    def _update_counter(self, text: str) -> None:
        if self._counter_label:
            self._counter_label.config(text=text)

    def _destroy_counter(self) -> None:
        if self._counter_win:
            try:
                self._counter_win.destroy()
            except Exception:
                pass
            self._counter_win = None
            self._counter_label = None

    # ── 恢复桌宠 ────────────────────────────
    def _restore_pet(self) -> None:
        if self._saved_pos:
            self.pet.x, self.pet.y = self._saved_pos
            try:
                self.pet._move()
            except Exception:
                pass
        try:
            self.pet._set_pet_image(self._saved_img or "stay")
        except Exception:
            pass

    # ── 结束（清理后播报结算） ────────────────
    def _finish(self, text: str, duration: int = 6000) -> None:
        self.stop()
        self.pet.show_talk(text)
        self.pet.root.after(duration, self.pet.hide_talk)
        gm = getattr(self.pet, "game_manager", None)
        if gm is not None and getattr(gm, "_active", None) is self:
            gm._active = None
