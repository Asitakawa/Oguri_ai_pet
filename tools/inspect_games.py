"""小游戏体检：命中测试 / 窗口几何 / 回合超时（开发用，不参与 pytest）"""
import ctypes
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import tkinter as tk

from game.dash_run.game import DashRunGame
from game.eating_rush.game import EatingRushGame
from game.fishing.game import FishingGame
from game.onigiri_catch.game import OnigiriCatchGame

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

user32 = ctypes.windll.user32


class FakeGameManager:
    _active = None


class FakePet:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.screen_w = root.winfo_screenwidth()
        self.screen_h = root.winfo_screenheight()
        self.pet_size = (180, 180)
        self.x = self.screen_w - 180 - 80
        self.y = self.screen_h - 180 - 80
        self.label = tk.Label(root, width=180, height=180, bg="lightgray", text="PET")
        self.label.pack()
        self._cur_img_key = None
        self.game_manager = FakeGameManager()

    def _move(self):
        self.root.geometry(f"+{int(self.x)}+{int(self.y)}")

    def _set_pet_image(self, key, auto_reset=None):
        self._cur_img_key = key
        self.label.config(text=f"[{key}]")

    def show_talk(self, text):
        pass

    def hide_talk(self):
        pass

    def eat_action(self, callback=None):
        if callback:
            self.root.after(120, callback)

    def tilt_head(self, callback=None):
        if callback:
            self.root.after(120, callback)

    def start_bounce_animation(self):
        pass


def _pump(root, seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.016)


def _win_info(root):
    return {
        "root": hex(root.winfo_id()),
        "root_geo": root.winfo_geometry(),
    }


def _overlay_info(game):
    ov = getattr(game, "_overlay", None)
    if ov is None or not ov.winfo_exists():
        return None
    ov.update_idletasks()
    return {
        "hwnd": hex(ov.winfo_id()),
        "geo": (ov.winfo_x(), ov.winfo_y(), ov.winfo_width(), ov.winfo_height()),
    }


def _hit(overlay_hwnd, root_hwnd, pt):
    h = user32.WindowFromPoint(pt[0], pt[1])
    if h == overlay_hwnd:
        return "OVERLAY(被拦截)"
    if h == root_hwnd:
        return "PET/ROOT"
    return f"other:{hex(h)}"


def inspect_game(cls, name):
    root = tk.Tk()
    root.geometry("+120+120")
    root.attributes("-topmost", True)
    root.update()
    pet = FakePet(root)
    root.update()
    game = cls(pet)
    game.start()
    root.update()
    _pump(root, 0.4)
    ov = _overlay_info(game)
    root_hwnd = root.winfo_id()
    ov_hwnd = ov["hwnd"] if ov else None
    print(f"\n===== {name} =====")
    print(f"  屏幕: {pet.screen_w}x{pet.screen_h} | 桌宠 pos=({int(pet.x)},{int(pet.y)}) size={pet.pet_size}")
    print(f"  桌宠底边距屏幕底: {pet.screen_h - (pet.y + pet.pet_size[1])}px")
    if ov:
        x, y, w, h = ov["geo"]
        print(f"  覆盖层: pos=({x},{y}) size={w}x{h} -> 覆盖整个屏幕? {w >= pet.screen_w and h >= pet.screen_h}")
        pet_c = (int(pet.x + 90), int(pet.y + 90))
        corner = (5, 5)
        taskbar = (int(pet.screen_w / 2), pet.screen_h - 10)
        print(f"  点击桌宠中心 {pet_c} -> {_hit(ov_hwnd, root_hwnd, pet_c)}")
        print(f"  点击左上角 {corner} -> {_hit(ov_hwnd, root_hwnd, corner)}")
        print(f"  点击屏幕底部 {taskbar} -> {_hit(ov_hwnd, root_hwnd, taskbar)}")
        # 检查点击穿透样式位是否设置（GetParent(winfo_id) 即 TkTopLevel 句柄）
        try:
            ex = user32.GetWindowLongW(user32.GetParent(game._overlay.winfo_id()), -20)
            print(f"  WS_EX_TRANSPARENT(0x20) 已设置? {bool(ex & 0x20)}")
        except Exception as e:
            print(f"  样式检查失败: {e}")
    else:
        print("  无覆盖层")
    game.stop()
    root.destroy()


def test_fishing_stale_timeout():
    """验证：上一回合的滞留超时是否会误判到下一回合。"""
    import game.fishing.game as fishing_mod
    from game.rules import FishingRules

    old_round = FishingRules.ROUND_SECONDS
    old_result = FishingRules.RESULT_SECONDS
    FishingRules.ROUND_SECONDS = 2.0
    FishingRules.RESULT_SECONDS = 0.3

    root = tk.Tk()
    root.geometry("+120+120")
    root.update()
    pet = FakePet(root)
    root.update()
    game = fishing_mod.FishingGame(pet)
    game.start()
    root.update()
    t0 = time.time()
    # 0.5s 时提前收竿（第一回合）
    while time.time() - t0 < 0.5:
        root.update()
        time.sleep(0.016)
    game._on_cast()
    print("\n===== fishing 滞留超时检测 =====")
    print(f"  提前收竿后 phase={game._phase} counts={game._counts} round={game._round_no}")
    # 推进 2.6s：跨越第一回合的超时点(2.0s)与结果期(0.3s)
    while time.time() - t0 < 2.6:
        root.update()
        time.sleep(0.016)
    print(f"  t=2.6s: round={game._round_no} phase={game._phase} counts={game._counts}")
    # 再看第二回合是否被第一回合的滞留超时误判为 miss
    stale_miss = game._round_no >= 3 or game._counts["miss"] > 1
    print(f"  第二回合出现滞留误判? {stale_miss} (round={game._round_no}, miss={game._counts['miss']})")
    game.stop()
    root.destroy()
    FishingRules.ROUND_SECONDS = old_round
    FishingRules.RESULT_SECONDS = old_result
    return stale_miss


if __name__ == "__main__":
    inspect_game(OnigiriCatchGame, "onigiri_catch")
    inspect_game(EatingRushGame, "eating_rush")
    inspect_game(DashRunGame, "dash_run")
    inspect_game(FishingGame, "fishing")
    stale = test_fishing_stale_timeout()
    print("\nFISHING_STALE_BUG:", stale)
