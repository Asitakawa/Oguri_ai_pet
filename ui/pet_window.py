"""小栗帽桌面宠物 — 主窗口 + 生命周期 + 事件路由"""
import gc
import math
import os
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import Menu, messagebox

from core import config as cfg
from core.ai_client import AIClient
from core.chat_history import ChatHistoryManager
from core.paths import get_data_path, get_resource_path
from core.pet_state import PetStatus
from core.reminder import ScheduleManager
from core.web_server import ManagementServer
from core.skill_system.manager import SkillManager
from game import GameManager
from ui.animations import AnimationMixin
from ui.bubble import ChatBubble
from ui.dialogs import UIDialogs
from ui.input_bar import InputBar
from ui.pet_sprite import PetSprite
from ui.status_bar import StatusBar


def _load_psutil():
    try:
        return __import__("psutil")
    except ImportError:
        return None

class KurumiPet(AnimationMixin):
    def __init__(self):
        self._init_attrs()
        self.chat_history = ChatHistoryManager(
            get_data_path(cfg.CHAT_HISTORY_FILE), cfg.MAX_HISTORY_LENGTH
        )
        self.ai = AIClient()
        self.dialogs = UIDialogs(self)
        self.schedule_manager = ScheduleManager(self)
        self.skill_manager = SkillManager(self)
        self.game_manager = GameManager(self)
        self.sprite = PetSprite(self)
        self.input_bar = InputBar(self)
        self.status = PetStatus()
        self.web_server = ManagementServer(self)
        self.web_server.start()
        self._activate_status_callbacks()
        self._init_monitoring()
        self._init_window()
        self._init_images()
        self._init_ui()
        self._bind_events()
        self._start_threads()
        self.root.mainloop()

    def _init_attrs(self):
        self.label = None
        self.current_img = None
        self.images = {}
        self.bubble = None
        self.status_bar = None
        self.menu = None
        self.default_pet_size = cfg.DEFAULT_PET_SIZE
        self.pet_size = self.default_pet_size
        self.scale_factor = 1.0
        self.pic_dir = get_resource_path("resources/images")
        self.is_auto_talking = False
        self.is_dialog_showing = False
        self._is_processing = False
        self.running = True
        self.is_dragging = False
        self.velocity_x = 0
        self.velocity_y = 0
        self._vx_buf = []
        self._vy_buf = []
        self.inertia_active = False
        self.is_hovering = False
        self.shake_animation = False
        self.bounce_animation = False
        self._hide_timer = None
        self._click_timer = None
        self._shown_click = False
        self._api_talking = False
        self.min_auto_reply_time = cfg.MIN_AUTO_REPLY
        self.max_auto_reply_time = cfg.MAX_AUTO_REPLY
        self.preset_min_interval = cfg.PRESET_MIN_INTERVAL
        self.preset_max_interval = cfg.PRESET_MAX_INTERVAL
        self.shake_intensity = cfg.SHAKE_INTENSITY
        self.bounce_height = cfg.BOUNCE_HEIGHT
        self.min_scale = cfg.MIN_SCALE
        self.max_scale = cfg.MAX_SCALE

    def _init_monitoring(self):
        self.start_time = time.time()
        self.gc_counter = 0
        self.error_log = []
        threading.Thread(target=self._memory_monitor, daemon=True).start()

    # ── 窗口 ──────────────────────────────────
    def _init_window(self):
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(2)
            self.root = tk.Tk()
            self.root.tk.call('tk', 'scaling', 1.5)
        except Exception:
            self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', 'black')
        self.root.config(bg='black')
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.x = self.screen_w - self.pet_size[0] - 50
        self.y = self.screen_h - self.pet_size[1] - 50
        self.root.geometry(f"{self.pet_size[0]}x{self.pet_size[1]}+{int(self.x)}+{int(self.y)}")

    # ── 图片 ──────────────────────────────────
    def _init_images(self):
        self.sprite.load_raw(self.pic_dir, self.pet_size)
        self.images = self.sprite.images
        self.current_img = self.sprite.current_img

    # ── UI ────────────────────────────────────
    def _init_ui(self):
        self.label = tk.Label(
            self.root, bd=0, highlightthickness=0, relief='flat',
            bg='black', image=self.current_img,
        )
        self.label.pack(fill='both', expand=True)
        self.bubble = ChatBubble(self)
        self.bubble.recalc_offsets()

    # ── 事件 ──────────────────────────────────
    def _bind_events(self):
        self.label.bind("<ButtonPress-1>", self._on_drag_start)
        self.label.bind("<B1-Motion>", self._on_drag_move)
        self.label.bind("<ButtonRelease-1>", self._on_drag_end)
        self.label.bind("<Enter>", self._on_enter)
        self.label.bind("<Leave>", self._on_leave)
        self.label.bind("<Double-Button-1>", self._on_double_click)
        self.label.bind("<Button-2>", self._on_middle_click)
        self.label.bind("<Button-3>", self._show_menu)
        self.label.bind("<MouseWheel>", lambda e: None)
        self._build_menu()

    def _build_menu(self):
        if self.menu:
            try:
                self.menu.destroy()
            except Exception:
                pass
        m = self.menu = Menu(self.root, tearoff=0, font=(cfg.FONT_FAMILY, 10),
                             bg=cfg.C_BG, fg=cfg.C_TEXT, activebackground=cfg.C_CREAM,
                             activeforeground=cfg.C_WOOD, relief='flat', bd=0)

        m.add_command(label="💬 对话", command=self.input_bar.show)
        m.add_command(label="🍙 喂饭团", command=self._feed_pet)
        m.add_separator()

        sub = Menu(m, tearoff=0, font=(cfg.FONT_FAMILY, 10),
                   bg=cfg.C_BG, fg=cfg.C_TEXT, activebackground=cfg.C_CREAM,
                   activeforeground=cfg.C_WOOD, relief='flat', bd=0)
        sub.add_command(label="📊 查看状态", command=self._toggle_status_bar)
        sub.add_command(label="📋 聊天记录", command=self.dialogs.show_chat_history)
        sub.add_command(label="🗑 清空记录", command=self._clear_chat_history)
        m.add_cascade(label="📋 记录", menu=sub)

        sub = Menu(m, tearoff=0, font=(cfg.FONT_FAMILY, 10),
                   bg=cfg.C_BG, fg=cfg.C_TEXT, activebackground=cfg.C_CREAM,
                   activeforeground=cfg.C_WOOD, relief='flat', bd=0)
        sub.add_command(label="📏 调整大小", command=self.dialogs.show_size_menu)
        sub.add_command(label="⚡ 技能管理", command=self.dialogs.show_skill_manager)
        sub.add_command(label="🔑 API 设置", command=self.dialogs.show_api_settings)
        sub.add_command(label="🔤 字体设置", command=self.dialogs.show_font_settings)
        sub.add_command(label="⚙ 系统设置", command=self.dialogs.show_settings)
        m.add_cascade(label="⚙ 设置", menu=sub)

        # 小游戏子菜单
        gsub = Menu(m, tearoff=0, font=(cfg.FONT_FAMILY, 10),
                    bg=cfg.C_BG, fg=cfg.C_TEXT, activebackground=cfg.C_CREAM,
                    activeforeground=cfg.C_WOOD, relief='flat', bd=0)
        gsub.add_command(label="🎮 游戏管理", command=self.dialogs.show_game_manager)
        enabled = self.game_manager.list_enabled()
        if enabled:
            gsub.add_separator()
            for key, gname in enabled:
                gsub.add_command(label=gname, command=lambda k=key: self._toggle_game(k))
        if self.game_manager.is_active():
            gsub.add_separator()
            gsub.add_command(label="⏹ 退出游戏", command=self.game_manager.stop)
        m.add_cascade(label="🎮 小游戏", menu=gsub)

        m.add_separator()
        m.add_command(label="🔄 重启", command=self.restart)
        m.add_command(label="🚪 退出", command=self.quit)

    def _toggle_game(self, key):
        if self.game_manager.is_active():
            self.game_manager.stop()
        self.game_manager.start(key)

    def _show_menu(self, e):
        self._build_menu()
        self.menu.post(e.x_root, e.y_root)

    def _activate_status_callbacks(self):
        def on_hunger_low():
            if not self.is_dialog_showing and not self._api_talking:
                t = random.choice(cfg.HUNGRY_TALK_TEXTS)
                self.root.after(0, lambda: self.show_talk(t))
                self.root.after(3000, self.hide_talk)

        def on_energy_low():
            if not self.is_dialog_showing and not self._api_talking:
                t = random.choice(cfg.TIRED_TALK_TEXTS)
                self.root.after(0, lambda: self.nap_action())
                self.root.after(0, lambda: self.show_talk(t))
                self.root.after(5000, self.hide_talk)

        self.status._on_hunger_low = on_hunger_low
        self.status._on_energy_low = on_energy_low

    def _feed_pet(self):
        self.status.feed()
        self.show_talk(random.choice(cfg.FEED_TALK_TEXTS))
        self.eat_action(callback=lambda: self.root.after(500, self.hide_talk))

    def _toggle_status_bar(self):
        if not self.status_bar:
            self.status_bar = StatusBar(self)
        if self.status_bar.visible:
            self.status_bar.hide()
        else:
            self.status_bar.show()
            self.root.after(5000, self.status_bar.hide)

    def _set_pet_image(self, key, auto_reset=None):
        if not self.label or key == getattr(self, '_cur_img_key', None):
            return
        self.sprite.set_image(key)
        self._cur_img_key = key
        if hasattr(self, '_reset_timer') and self._reset_timer:
            self.root.after_cancel(self._reset_timer)
            self._reset_timer = None
        if auto_reset:
            self._reset_timer = self.root.after(
                auto_reset, lambda: self._set_pet_image(
                    "talk" if self.is_dialog_showing else
                    "touch" if self.is_hovering else "stay"
                )
            )

    def _show_click_image(self):
        self._set_pet_image("click", auto_reset=1500)
        self._shown_click = True

    def _cancel_click_timer(self):
        if self._click_timer:
            self.root.after_cancel(self._click_timer)
            self._click_timer = None

    # ── 拖动 ──────────────────────────────────
    def _on_drag_start(self, e):
        self._cancel_click_timer()
        self._shown_click = False
        self.is_dragging = True
        self.inertia_active = False
        self.drag_offset_x = e.x
        self.drag_offset_y = e.y
        self.velocity_x = 0
        self.velocity_y = 0
        self._vx_buf.clear()
        self._vy_buf.clear()
        self.stop_all_animations()
        self.status.spend_energy()
        self._click_timer = self.root.after(180, self._show_click_image)

    def _on_drag_move(self, e):
        if self.is_dragging:
            if not self._shown_click:
                self._cancel_click_timer()
                self._show_click_image()
            nx = e.x_root - self.drag_offset_x
            ny = e.y_root - self.drag_offset_y
            vx = nx - self.x
            vy = ny - self.y
            self._vx_buf.append(vx)
            self._vy_buf.append(vy)
            if len(self._vx_buf) > 3:
                self._vx_buf.pop(0)
                self._vy_buf.pop(0)
            self.velocity_x = sum(self._vx_buf) / len(self._vx_buf)
            self.velocity_y = sum(self._vy_buf) / len(self._vy_buf)
            self.x = max(0, min(nx, self.screen_w - self.pet_size[0]))
            self.y = max(0, min(ny, self.screen_h - self.pet_size[1]))
            self.root.geometry(f"+{int(self.x)}+{int(self.y)}")
            self.bubble.update_position()
            self.input_bar._update_pos()
            if self.status_bar and self.status_bar.visible:
                self.status_bar._position()

    def _on_drag_end(self, e):
        self._cancel_click_timer()
        self.is_dragging = False
        speed = math.sqrt(self.velocity_x ** 2 + self.velocity_y ** 2)
        if speed > 6:
            self.inertia_active = True
            self.apply_inertia()
        if not self.inertia_active and self.label.winfo_containing(e.x_root, e.y_root) == self.label:
            self._set_pet_image("talk" if self.is_dialog_showing else "touch", auto_reset=1000)
            self.start_shake_animation()
        else:
            self._set_pet_image("talk" if self.is_dialog_showing else "stay")
        self.bubble.update_position(force=True)

    def _on_enter(self, e):
        if not self.is_dragging and not self.is_auto_talking and not self._api_talking:
            self.is_hovering = True
            self._set_pet_image("talk" if self.is_dialog_showing else "touch")

    def _on_leave(self, e):
        if not self.is_dragging and not self.is_auto_talking and not self._api_talking:
            self.is_hovering = False
            self._set_pet_image("talk" if self.is_dialog_showing else "stay")

    def _on_double_click(self, e):
        if self.is_dragging:
            return
        now = time.time()
        if now - getattr(self, 'last_click_time', 0) < 0.5:
            self.start_bounce_animation()
            self._trigger_special_talk()
        else:
            self.start_shake_animation()
            self._trigger_talk()
        self.last_click_time = now

    def _on_middle_click(self, e):
        self.show_talk(cfg.SCREENSHOT_START)
        threading.Thread(target=self._process_screenshot_analysis, daemon=True).start()

    # ── 气泡 ──────────────────────────────────
    def show_talk(self, text):
        self.is_dialog_showing = True
        self.bubble.show(text)
        print(f"💬 {text}")

    def hide_talk(self):
        if hasattr(self, '_hide_timer') and self._hide_timer:
            self.root.after_cancel(self._hide_timer)
            self._hide_timer = None
        self.is_dialog_showing = False
        self.bubble.hide()
        self._set_pet_image("touch" if self.is_hovering else "stay")
        print("💬 对话结束")

    def _trigger_talk(self):
        if self.is_dialog_showing:
            self.show_talk(random.choice(cfg.CLICK_RESPONSES))
        else:
            self.show_talk(cfg.FIRST_CLICK)
        self._reset_hide_timer(3000)

    def _trigger_special_talk(self):
        if self.is_dialog_showing:
            self.show_talk(random.choice(cfg.SPECIAL_CLICK_RESPONSES))
        else:
            self.show_talk(cfg.FIRST_SPECIAL_CLICK)
        self._reset_hide_timer(4000)

    def _reset_hide_timer(self, delay):
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)
        self._hide_timer = self.root.after(delay, self.hide_talk)

    # ── 截图分析 ──────────────────────────────
    def _process_screenshot_analysis(self):
        from core.prompts import SCREENSHOT_SYSTEM_PROMPT
        try:
            self.root.after(0, lambda: self.show_talk(cfg.SCREENSHOT_LOADING))
            img = AIClient.capture_screen()
            if not img:
                self.root.after(0, lambda: self.show_talk(cfg.SCREENSHOT_FAIL))
                self.root.after(3000, self.hide_talk)
                return
            prompt = SCREENSHOT_SYSTEM_PROMPT
            r = self.ai.call(prompt, img, history_context=None, max_retries=2)
            if r:
                self.root.after(0, lambda: self.show_talk(r))
                self.root.after(6000, self.hide_talk)
            else:
                self.root.after(0, lambda: self.show_talk(
                    random.choice(cfg.FALLBACK_SCREENSHOT_RESPONSES)))
                self.root.after(4000, self.hide_talk)
        except Exception as e:
            print(f"截图分析出错: {e}")
            self.root.after(0, lambda: self.show_talk(cfg.SCREENSHOT_ERROR))
            self.root.after(3000, self.hide_talk)

    # ── AI 响应 ───────────────────────────────
    def _process_ai_response(self, user_message, with_screenshot):
        self._is_processing = True
        try:
            ctx = self.chat_history.get_context(cfg.MEMORY_CONTEXT_SIZE)
            if user_message:
                self.chat_history.add("user", user_message)
            r, _ = self.ai.ask(
                user_message or "看看屏幕",
                with_screenshot,
                history_context=ctx,
                tools=self.skill_manager.get_tools(),
                execute_tool=self.skill_manager.execute,
            )
            self.chat_history.add("assistant", r)
            self.root.after(0, lambda: self._handle_ai_response(r))
        except Exception as e:
            print(f"AI处理错误: {e}")
            r = "啊，出错了"
            self.chat_history.add("assistant", r)
            self.root.after(0, lambda: self._handle_ai_response(r))
        finally:
            self._is_processing = False

    def _handle_ai_response(self, text):
        if not text or not text.strip():
            text = "处理完成了"
        self.show_talk(text)
        self.root.after(6000, self.hide_talk)

    # ── 自动说话 ──────────────────────────────
    def _start_threads(self):
        threading.Thread(target=self._preset_talk_loop, daemon=True).start()
        threading.Thread(target=self._api_talk_loop, daemon=True).start()

    def _preset_talk_loop(self):
        def _say(text, anim=None):
            try:
                self.root.after(0, lambda: self.show_talk(text))
                if anim:
                    self.root.after(0, anim)
            except Exception:
                pass

        print("预设自动回复线程已启动, 初始问候等待10-20秒...")
        self._sleep_chunk(random.randint(10, 20))
        if self.running:
            self.is_auto_talking = True
            _say(random.choice(cfg.FALLBACK_TALK_TEXTS))
            time.sleep(cfg.AUTO_TALK_DURATION)
            self.root.after(0, self.hide_talk)
            self.is_auto_talking = False
            print("预设自动回复: 初始问候完成")

        while self.running:
            delay = random.randint(self.preset_min_interval, self.preset_max_interval)
            print(f"预设自动回复: 等待 {delay} 秒后下一轮")
            self._sleep_chunk(delay)
            if not self.running:
                break
            if self._api_talking or self._is_processing:
                continue
            try:
                self.is_auto_talking = True
                h = self.status.hunger_pct
                e = self.status.energy_pct
                r = random.random()
                if h < 30 and r < 0.4:
                    _say(random.choice(cfg.HUNGRY_TALK_TEXTS), self.tilt_head)
                elif e < 25 and r < 0.4:
                    _say(random.choice(cfg.TIRED_TALK_TEXTS),
                         lambda: self.nap_action(duration=1.5))
                else:
                    _say(random.choice(cfg.FALLBACK_TALK_TEXTS))
                time.sleep(cfg.AUTO_TALK_DURATION)
                self.root.after(0, self.hide_talk)
            except Exception:
                pass
            finally:
                self.is_auto_talking = False

    def _api_talk_loop(self):
        def _say(text):
            try:
                self.root.after(0, lambda: self.show_talk(text))
            except Exception:
                pass

        print(f"AI自动回复线程已启动, 是否配置: {self.ai.is_configured}")
        while self.running:
            delay = random.randint(self.min_auto_reply_time, self.max_auto_reply_time)
            print(f"AI自动回复: 等待 {delay} 秒后检查")
            self._sleep_chunk(delay)
            if not self.running:
                break
            if not self.ai.is_configured:
                continue
            if self._is_processing:
                print("AI自动回复: 用户正在对话中, 跳过本轮")
                continue
            try:
                self._api_talking = True
                ctx = self.chat_history.get_context(10)
                text = self.ai.auto_talk_prompt(history_context=ctx)
                _say(text)
                self.root.after(0, self.tilt_head)
                time.sleep(cfg.AUTO_TALK_DURATION)
                self.root.after(0, self.hide_talk)
            except Exception:
                pass
            finally:
                self._api_talking = False

    def _sleep_chunk(self, total):
        remaining = total
        while remaining > 0 and self.running:
            chunk = min(2, remaining)
            time.sleep(chunk)
            remaining -= chunk

    # ── 缩放 ──────────────────────────────────
    def _resize_pet(self, factor):
        if factor < self.min_scale or factor > self.max_scale:
            return
        self.scale_factor = factor
        self.pet_size = (
            int(self.default_pet_size[0] * factor),
            int(self.default_pet_size[1] * factor),
        )
        self.sprite.load_raw(self.pic_dir, self.pet_size)
        self.images = self.sprite.images
        self.current_img = self.sprite.current_img
        if self.label:
            self.label.config(image=self.current_img)
        self.root.geometry(
            f"{self.pet_size[0]}x{self.pet_size[1]}+{int(self.x)}+{int(self.y)}"
        )
        self.bubble.recalc_offsets()
        self.bubble.update_position(force=True)
        self.shake_intensity = int(3 * factor)
        self.bounce_height = int(10 * factor)

    def _clear_chat_history(self):
        if messagebox.askyesno("确认", "确定要清空所有聊天记录吗？"):
            self.chat_history.clear()
            self.show_talk(cfg.HISTORY_CLEARED)

    # ── 内存监控 ──────────────────────────────
    def _memory_monitor(self):
        while self.running:
            time.sleep(cfg.MEMORY_CHECK_INTERVAL)
            try:
                try:
                    psutil = _load_psutil()
                    if psutil:
                        mem = psutil.Process(os.getpid()).memory_info().rss
                        if mem > cfg.MAX_MEMORY_USAGE:
                            gc.collect()
                            self.gc_counter += 1
                except Exception:
                    pass
                uptime = time.time() - self.start_time
                if int(uptime) % 3600 < 60:
                    h = int(uptime // 3600)
                    m = int((uptime % 3600) // 60)
                    print(f"📊 运行: {h}h{m}m | 消息: {len(self.chat_history)} | GC: {self.gc_counter}")
            except Exception:
                time.sleep(60)

    def get_system_info(self):
        info = {
            "运行时间": f"{int((time.time() - self.start_time) // 3600)}小时",
            "聊天记录": len(self.chat_history),
            "GC执行次数": self.gc_counter,
            "错误数量": len(self.error_log),
        }
        psutil = _load_psutil()
        if psutil:
            try:
                info["内存使用"] = f"{psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024):.1f}MB"
            except Exception:
                info["内存使用"] = "不可用"
        else:
            info["内存使用"] = "不可用"
        return info

    # ── 重启 ──────────────────────────────────
    def restart(self):
        self.chat_history.save(sync=True)
        self.schedule_manager.stop()
        self.status.stop()
        if getattr(self, "web_server", None):
            self.web_server.stop()
        args = [sys.executable]
        if not getattr(sys, "frozen", False):
            args.append(os.path.abspath("main.py"))
        args.append("--restart")
        subprocess.Popen(args)
        self.root.destroy()

    # ── 退出 ──────────────────────────────────
    def quit(self):
        if not getattr(self, '_quitting', False):
            self._quitting = True
        else:
            return
        print("正在退出程序...")
        self.running = False
        self.stop_all_animations()
        self.status.stop()
        if getattr(self, "web_server", None):
            self.web_server.stop()
        self.schedule_manager.stop()
        self.chat_history.save(sync=True)

        info = self.get_system_info()
        hrs = int((time.time() - self.start_time) // 3600)
        mins = int(((time.time() - self.start_time) % 3600) // 60)

        msgs = [
            cfg.GOODBYE_MESSAGES[0].format(hrs=hrs, mins=mins),
            cfg.GOODBYE_MESSAGES[1].format(msgs=info['聊天记录']),
            cfg.GOODBYE_MESSAGES[2],
            cfg.GOODBYE_MESSAGES[3],
        ]
        self.show_talk(random.choice(msgs))

        delay = max(3000, len(random.choice(msgs)) * 150)
        self.root.after(delay, lambda: (
            self.hide_talk(),
            print(f"\n📊 运行统计:\n• 运行: {hrs}h{mins}m\n• 消息: {info['聊天记录']}条\n• GC: {info['GC执行次数']}次\n👋 已退出"),
            self.root.after(500, self.root.destroy),
        ))

    def __del__(self):
        try:
            self.running = False
            if hasattr(self, 'root') and self.root:
                self.root.destroy()
        except Exception:
            pass
