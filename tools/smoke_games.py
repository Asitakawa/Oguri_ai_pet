"""小游戏冒烟测试：真实 Tk 窗口驱动四个游戏并截图（开发用，不参与 pytest）"""
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import tkinter as tk

from PIL import ImageGrab

from game.dash_run.game import DashRunGame
from game.eating_rush.game import EatingRushGame
from game.fishing.game import FishingGame
from game.onigiri_catch.game import OnigiriCatchGame

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

OUT_DIR = pathlib.Path(r"C:\Users\Arelq_\.codex\visualizations\2026\08\04\019fcba0-2abb-7660-9f91-cd03537a1e49")
OUT_DIR.mkdir(parents=True, exist_ok=True)


class FakeGameManager:
    _active = None


class FakePet:
    """复刻游戏依赖的桌宠 API 表面。"""

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
        print(f"  TALK: {text}")

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


def run_game(cls, name, setup, seconds=1.8):
    root = tk.Tk()
    root.geometry("+120+120")
    root.attributes("-topmost", True)
    root.update()
    pet = FakePet(root)
    root.update()
    game = cls(pet)
    print(f"\n===== {name} =====")
    try:
        game.start()
        root.update()
        _pump(root, 0.4)
        if setup:
            setup(game, pet)
        _pump(root, seconds)
        root.update()
        shot = OUT_DIR / f"{name}.png"
        img = ImageGrab.grab(bbox=(0, 0, pet.screen_w, pet.screen_h))
        img.save(shot)
        print(f"  screenshot -> {shot}")
    except Exception:
        traceback.print_exc()
    finally:
        try:
            game.stop()
        except Exception:
            traceback.print_exc()
        try:
            root.destroy()
        except Exception:
            pass
    return game


def setup_catch(game, pet):
    pet.x = 400
    pet._move()


def setup_eating(game, pet):
    for _ in range(12):
        game._on_bite()


def setup_dash(game, pet):
    game._on_jump()
    time.sleep(0.2)


def setup_fishing(game, pet):
    time.sleep(0.8)


if __name__ == "__main__":
    run_game(OnigiriCatchGame, "onigiri_catch", setup_catch, seconds=1.6)
    run_game(EatingRushGame, "eating_rush", setup_eating, seconds=1.0)
    run_game(DashRunGame, "dash_run", setup_dash, seconds=1.8)
    run_game(FishingGame, "fishing", setup_fishing, seconds=1.6)
    print("\nDONE")
