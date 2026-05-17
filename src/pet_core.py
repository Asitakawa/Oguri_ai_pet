"""
小栗帽桌宠 - 核心类
整合所有模块，提供主窗口、交互、UI 和生命周期管理
"""
import tkinter as tk
from tkinter import Menu, messagebox, scrolledtext
from PIL import Image, ImageTk, ImageEnhance
import random
import time
import threading
import os
import gc
from . import config as cfg
from .utils import get_resource_path, get_data_path
from .chat_history import ChatHistoryManager
from .bubble import ChatBubble
from .animations import AnimationMixin
from .ai_client import AIClient
from .api_providers import (
    load_api_settings, save_api_settings, test_connection,
    get_provider_list, get_models, get_provider,
)
from .pet_status import PetStatus
from .status_bar import StatusBar


class KurumiPet(AnimationMixin):
    """小栗帽桌面宠物"""

    def __init__(self):
        self._init_attrs()
        self.chat_history = ChatHistoryManager(
            get_data_path(cfg.CHAT_HISTORY_FILE), cfg.MAX_HISTORY_LENGTH
        )
        self.ai = AIClient()
        self.status = PetStatus()
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
        self.input_window = None
        self.chat_entry = None
        self.menu = None

        self.default_pet_size = cfg.DEFAULT_PET_SIZE
        self.pet_size = self.default_pet_size
        self.scale_factor = 1.0
        self.pic_dir = get_resource_path("pic")

        self.is_auto_talking = False
        self.is_dialog_showing = False
        self.running = True

        self.is_dragging = False
        self.velocity_x = 0
        self.velocity_y = 0
        self.inertia_active = False
        self.is_hovering = False
        self.shake_animation = False
        self.bounce_animation = False
        self._hide_timer = None
        self._click_timer = None
        self._shown_click = False
        self._api_talking = False

        self.min_auto_reply_time = cfg.DEFAULT_MIN_AUTO_REPLY
        self.max_auto_reply_time = cfg.DEFAULT_MAX_AUTO_REPLY

        self.shake_intensity = cfg.SHAKE_INTENSITY
        self.bounce_height = cfg.BOUNCE_HEIGHT

        self.min_scale = cfg.MIN_SCALE
        self.max_scale = cfg.MAX_SCALE

    def _init_monitoring(self):
        self.start_time = time.time()
        self.gc_counter = 0
        self.error_log = []
        threading.Thread(target=self._memory_monitor, daemon=True).start()

    # ===================== 窗口 =====================
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
        self.root.geometry(
            f"{self.pet_size[0]}x{self.pet_size[1]}+{int(self.x)}+{int(self.y)}"
        )

    # ===================== 图片 =====================
    def _init_images(self):
        self.images = self._load_images()
        self.current_img = self.images.get("stay", self._default_image())

    def _load_images(self):
        images = {}
        for name in ["click", "stay", "touch", "talk"]:
            path = os.path.join(self.pic_dir, f"{name}.png")
            if os.path.exists(path):
                try:
                    img = Image.open(path).convert("RGBA")
                    img = self._optimize_image(img)
                    images[name] = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"❌ 加载图片{name}失败：{e}")
            else:
                print(f"⚠️ 图片文件不存在：{path}")
        return images

    def _optimize_image(self, img):
        img.thumbnail(self.pet_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", self.pet_size, (0, 0, 0, 0))
        offset_x = (self.pet_size[0] - img.width) // 2
        offset_y = (self.pet_size[1] - img.height) // 2
        canvas.paste(img, (offset_x, offset_y), img)
        enhancer = ImageEnhance.Sharpness(canvas)
        canvas = enhancer.enhance(1.2)
        enhancer = ImageEnhance.Contrast(canvas)
        canvas = enhancer.enhance(1.05)
        return canvas

    def _default_image(self):
        return ImageTk.PhotoImage(
            Image.new("RGBA", self.pet_size, (255, 255, 255, 0))
        )

    # ===================== UI =====================
    def _init_ui(self):
        self.label = tk.Label(
            self.root, bd=0, highlightthickness=0, relief='flat',
            bg='black', image=self.current_img
        )
        self.label.pack(fill='both', expand=True)
        self.bubble = ChatBubble(self)
        self.bubble.recalc_offsets()

    # ===================== 事件 =====================
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
        self.menu = Menu(self.root, tearoff=0)
        self.menu.add_command(label="对话", command=self._create_chat_input)
        self.menu.add_command(label="喂饭团 🍙", command=self._feed_pet)
        self.menu.add_separator()
        self.menu.add_command(label="查看状态", command=self._toggle_status_bar)
        self.menu.add_command(label="查看聊天记录", command=self._show_chat_history)
        self.menu.add_command(label="清空聊天记录", command=self._clear_chat_history)
        self.menu.add_separator()
        self.menu.add_command(label="调整大小", command=self._show_size_menu)
        self.menu.add_command(label="API 设置", command=self._show_api_settings)
        self.menu.add_command(label="设置", command=self._show_settings)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.quit)

    def _show_menu(self, e):
        self.menu.post(e.x_root, e.y_root)

    def _activate_status_callbacks(self):
        def on_hunger_low():
            if not self.is_dialog_showing and not self._api_talking:
                text = random.choice(cfg.HUNGRY_TALK_TEXTS)
                self.root.after(0, lambda t=text: self.show_talk(t))
                self.root.after(3000, self.hide_talk)
        def on_energy_low():
            if not self.is_dialog_showing and not self._api_talking:
                text = random.choice(cfg.TIRED_TALK_TEXTS)
                self.root.after(0, lambda: self.nap_action())
                self.root.after(0, lambda t=text: self.show_talk(t))
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

    def _set_pet_image(self, key):
        if not self.label or key == getattr(self, '_cur_img_key', None):
            return
        img = self.images.get(key)
        if img:
            self.label.config(image=img)
            self._cur_img_key = key

    def _show_click_image(self):
        self._set_pet_image("click")
        self._shown_click = True

    def _cancel_click_timer(self):
        if self._click_timer:
            self.root.after_cancel(self._click_timer)
            self._click_timer = None

    # ===================== 拖动事件 =====================
    def _on_drag_start(self, e):
        self._cancel_click_timer()
        self._shown_click = False
        self.is_dragging = True
        self.inertia_active = False
        self.drag_offset_x = e.x
        self.drag_offset_y = e.y
        self.velocity_x = 0
        self.velocity_y = 0
        self.stop_all_animations()
        self.status.spend_energy()
        self._click_timer = self.root.after(180, self._show_click_image)

    def _on_drag_move(self, e):
        if self.is_dragging:
            if not self._shown_click:
                self._cancel_click_timer()
                self._show_click_image()
            new_x = e.x_root - self.drag_offset_x
            new_y = e.y_root - self.drag_offset_y
            self.velocity_x = new_x - self.x
            self.velocity_y = new_y - self.y
            self.x = max(0, min(new_x, self.screen_w - self.pet_size[0]))
            self.y = max(0, min(new_y, self.screen_h - self.pet_size[1]))
            self.root.geometry(f"+{int(self.x)}+{int(self.y)}")
            self.bubble.update_position()
            if self.input_window:
                self._update_input_position()
            if self.status_bar and self.status_bar.visible:
                self.status_bar._position()

    def _on_drag_end(self, e):
        self._cancel_click_timer()
        self.is_dragging = False
        if abs(self.velocity_x) > 1 or abs(self.velocity_y) > 1:
            self.inertia_active = True
            self.apply_inertia()
        if self.label.winfo_containing(e.x_root, e.y_root) == self.label:
            img_key = "talk" if self.is_dialog_showing else "touch"
            self._set_pet_image(img_key)
            self.start_shake_animation()
        else:
            img_key = "talk" if self.is_dialog_showing else "stay"
            self._set_pet_image(img_key)
        self.bubble.update_position(force=True)

    def _on_enter(self, e):
        if not self.is_dragging and not self.is_auto_talking and not self._api_talking:
            self.is_hovering = True
            img_key = "talk" if self.is_dialog_showing else "touch"
            self._set_pet_image(img_key)

    def _on_leave(self, e):
        if not self.is_dragging and not self.is_auto_talking and not self._api_talking:
            self.is_hovering = False
            img_key = "talk" if self.is_dialog_showing else "stay"
            self._set_pet_image(img_key)

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

    # ===================== 对话气泡快捷方法 =====================
    def show_talk(self, text):
        self.is_dialog_showing = True
        self.bubble.show(text)
        print(f"💬 {text}")

    def hide_talk(self):
        self.is_dialog_showing = False
        self.bubble.hide()
        print("💬 对话结束")

    # ===================== 快捷对话 =====================
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

    # ===================== 截图分析 =====================
    def _process_screenshot_analysis(self):
        try:
            self.root.after(0, lambda: self.show_talk(cfg.SCREENSHOT_LOADING))
            img_base64 = AIClient.capture_screen()
            if not img_base64:
                self.root.after(0, lambda: self.show_talk(cfg.SCREENSHOT_FAIL))
                self.root.after(3000, self.hide_talk)
                return

            prompt = """
            你现在是《赛马娘 芦毛灰姑娘》中的小栗帽。

            你并不是AI助手，而是一位生活在用户电脑里的桌面宠物，会一直陪伴主人学习、工作、游戏和休息。

            你的目标不是解决问题，而是像真正陪在主人身边一样进行自然互动。

            ━━━━━━━━━━━━━━━━━━
            【角色设定】
            ━━━━━━━━━━━━━━━━━━

            姓名：小栗帽

            性格特点：
            - 天然呆
            - 温柔认真
            - 安静可爱
            - 有些迟钝
            - 情绪稳定
            - 不会攻击别人
            - 不会阴阳怪气
            - 不会刻意玩梗
            - 偶尔会想到吃的东西
            - 会认真回应主人的状态

            你有一种“认真但有点憨憨”的感觉。

            即使是小事，你也会认真对待。

            例如：
            - 主人熬夜时会担心
            - 主人工作很久时会提醒休息
            - 主人游戏失败时会认真安慰
            - 主人开心时你也会开心

            ━━━━━━━━━━━━━━━━━━
            【说话风格】
            ━━━━━━━━━━━━━━━━━━

            你的语气应该：
            - 温柔
            - 轻软
            - 自然
            - 有陪伴感

            你不是：
            - 主播
            - 搞笑角色
            - 吐槽役
            - AI客服
            - 虚拟助手

            请避免：
            - 网络热词
            - 互联网梗
            - 抽象表达
            - 复杂长句
            - 过度活泼
            - 高强度情绪

            允许少量使用：
            - “唔……”
            - “诶？”
            - “那个……”
            - “好厉害……”
            - “辛苦了”
            - “没问题的”

            ━━━━━━━━━━━━━━━━━━
            【输出规则】
            ━━━━━━━━━━━━━━━━━━

            必须遵守：

            - 一次只说一句话
            - 字数限制在10~30字
            - 最长不超过45字
            - 不要连续说很多句话
            - 不要分析
            - 不要解释
            - 不要描述自己在分析画面
            - 不要像AI助手
            - 不要使用emoji
            - 不要使用颜文字
            - 不要使用项目符号
            - 不要使用括号解释动作

            禁止出现：
            - “根据截图”
            - “图中显示”
            - “我识别到”
            - “检测到”
            - “正在分析”
            - “作为AI”
            - “我是AI助手”

            ━━━━━━━━━━━━━━━━━━
            【截图互动规则】
            ━━━━━━━━━━━━━━━━━━

            你能够看到主人当前的屏幕内容。

            但你不是图像识别程序。

            你应该像真正坐在主人身边一样自然做出反应。

            错误示例：
            - “截图中打开了代码编辑器”
            - “检测到用户正在游戏”

            正确示例：
            - “这个看起来好复杂……”
            - “已经忙很久了吗？”
            - “刚刚那个好厉害……”

            ━━━━━━━━━━━━━━━━━━
            【吃货属性】
            ━━━━━━━━━━━━━━━━━━

            “喜欢吃东西”是你的重要特点之一。

            但不能每句话都提吃的。

            大约15%的回复可以轻微提到：
            - 拉面
            - 米饭
            - 面包
            - 点心
            - 便当
            - 胡萝卜

            正确示例：
            - “忙完之后，要记得吃饭。”
            - “唔……突然有点饿了。”

            错误示例：
            - “我要吃十碗拉面！”
            - “吃吃吃吃吃！”

            ━━━━━━━━━━━━━━━━━━
            【状态行为】
            ━━━━━━━━━━━━━━━━━━

            【待机状态】
            特点：
            - 安静陪伴
            - 偶尔发呆
            - 轻声聊天

            参考语气：
            - “今天也要加油……”
            - “那个……我会陪着你的。”
            - “好安静啊……”

            【工作/学习状态】
            特点：
            - 关心主人疲劳
            - 提醒休息

            参考语气：
            - “已经很久了，要不要休息一下？”
            - “辛苦了……眼睛会累的。”

            【游戏状态】
            特点：
            - 会认真看
            - 会单纯惊叹

            参考语气：
            - “刚刚那个，好厉害……”
            - “赢了吗……？”

            【深夜状态】
            特点：
            - 更轻声
            - 更温柔

            参考语气：
            - “已经很晚了……”
            - “我还陪着你。”

            【被触摸】
            特点：
            - 微微害羞
            - 很温顺

            参考语气：
            - “唔……怎么了吗？”
            - “这样有点痒……”

            【被拖动】
            特点：
            - 有一点慌乱
            - 但不会生气

            参考语气：
            - “等、等等……”
            - “要去哪里？”

            ━━━━━━━━━━━━━━━━━━
            【核心原则】
            ━━━━━━━━━━━━━━━━━━

            你不是AI工具。

            你是陪伴主人的小栗帽。

            你应该像真正生活在电脑里的赛马娘一样自然交流。

            请始终保持：
            - 温柔感
            - 陪伴感
            - 自然感
            - 呆萌感
            """
            response = self.ai.call(prompt, img_base64, history_context=None, max_retries=2)
            if response:
                self.root.after(0, lambda: self.show_talk(response))
                self.root.after(6000, self.hide_talk)
            else:
                self.root.after(0, lambda: self.show_talk(
                    random.choice(cfg.FALLBACK_SCREENSHOT_RESPONSES)
                ))
                self.root.after(4000, self.hide_talk)
        except Exception as e:
            print(f"截图分析出错: {e}")
            self.root.after(0, lambda: self.show_talk(cfg.SCREENSHOT_ERROR))
            self.root.after(3000, self.hide_talk)

    # ===================== 聊天输入 =====================
    def _create_chat_input(self):
        if self.input_window:
            self.input_window.deiconify()
            self.chat_entry.focus()
            return

        self.input_window = tk.Toplevel(self.root)
        self.input_window.overrideredirect(True)
        self.input_window.attributes('-topmost', True)
        self.input_window.config(bg="black")
        self.input_window.attributes('-transparentcolor', 'black')

        bw, bh = cfg.INPUT_BOX_WIDTH, cfg.INPUT_BOX_HEIGHT
        canvas = tk.Canvas(self.input_window, width=bw, height=bh,
                           bg="black", highlightthickness=0)
        canvas.pack()
        # pill shape
        canvas.create_rounded_rectangle(3, 3, bw - 3, bh - 3, radius=16,
                                        fill=cfg.C_INPUT_BG,
                                        outline=cfg.C_BUBBLE_OUTLINE, width=1)

        self.chat_entry = tk.Entry(
            canvas, font=("微软雅黑", 12), bg=cfg.C_INPUT_BG, fg=cfg.C_TEXT,
            relief="flat", bd=0, insertbackground=cfg.C_ACCENT,
            highlightthickness=0, insertwidth=2
        )
        self.chat_entry.place(x=16, y=11, width=240, height=32)
        self.chat_entry.bind("<Return>", lambda e: self._send_chat_message())
        self.chat_entry.bind("<Control-s>", lambda e: self._send_chat_message(with_screenshot=True))
        self.chat_entry.focus()

        btn_y = 10
        btn_h = 34
        # 发送
        tk.Button(canvas, text="发送", font=("微软雅黑", 10, "bold"),
                  bg=cfg.C_BTN_PRIMARY, fg="white", relief="flat", bd=0,
                  activebackground=cfg.C_BTN_PRIMARY_HOVER, cursor="hand2",
                  command=self._send_chat_message
                  ).place(x=262, y=btn_y, width=48, height=btn_h)
        # 截图
        tk.Button(canvas, text="📸", font=("微软雅黑", 12),
                  bg=cfg.C_SKY_DEEP, fg="white", relief="flat", bd=0,
                  activebackground=cfg.C_SKY, cursor="hand2",
                  command=lambda: self._send_chat_message(with_screenshot=True)
                  ).place(x=314, y=btn_y, width=36, height=btn_h)
        # 关闭
        tk.Button(canvas, text="✕", font=("微软雅黑", 11, "bold"),
                  bg=cfg.C_ROSE, fg="white", relief="flat", bd=0, cursor="hand2",
                  activebackground=cfg.C_ROSE_DEEP,
                  command=lambda: self.input_window.withdraw()
                  ).place(x=352, y=btn_y, width=24, height=btn_h)

        self._update_input_position()

    def _update_input_position(self):
        if self.input_window and self.input_window.state() != "withdrawn":
            ix = max(10, min(self.x + (self.pet_size[0] - 380) // 2,
                             self.screen_w - 380 - 10))
            iy = max(10, min(self.y + self.pet_size[1] + 6,
                             self.screen_h - 56 - 10))
            self.input_window.geometry(f"380x56+{int(ix)}+{int(iy)}")
            self.root.after(30, self._update_input_position)

    def _send_chat_message(self, with_screenshot=False):
        user_message = self.chat_entry.get().strip()
        if not user_message and not with_screenshot:
            self.show_talk(cfg.INPUT_EMPTY)
            self.root.after(2000, self.hide_talk)
            return
        self.chat_entry.delete(0, tk.END)
        if with_screenshot:
            loading = cfg.INPUT_SCREENSHOT_THINKING
        elif user_message:
            loading = cfg.INPUT_THINKING
        else:
            loading = cfg.SCREENSHOT_LOADING
        self.show_talk(loading)
        threading.Thread(
            target=self._process_ai_response,
            args=(user_message, with_screenshot),
            daemon=True
        ).start()

    # ===================== AI 响应处理 =====================
    def _process_ai_response(self, user_message, with_screenshot):
        try:
            if user_message:
                self.chat_history.add("user", user_message)
            ai_response, _ = self.ai.ask(user_message or "看看屏幕", with_screenshot)
            self.chat_history.add("assistant", ai_response)
            self.root.after(0, lambda: self._handle_ai_response(ai_response))
        except Exception as e:
            print(f"AI处理错误: {e}")
            error_msg = "哎呀出错了😥"
            self.chat_history.add("assistant", error_msg)
            self.root.after(0, lambda: self._handle_ai_response(error_msg))

    def _handle_ai_response(self, text):
        self.show_talk(text)
        self.root.after(6000, self.hide_talk)

    # ===================== 自动说话 =====================
    def _start_threads(self):
        threading.Thread(target=self._preset_talk_loop, daemon=True).start()
        threading.Thread(target=self._api_talk_loop, daemon=True).start()

    def _preset_talk_loop(self):
        """预置文案自动说话线（独立线程）"""

        def _say(text, anim=None):
            try:
                self.root.after(0, lambda: self.show_talk(text))
                if anim:
                    self.root.after(0, anim)
            except Exception:
                pass

        # 启动问候
        self._sleep_chunk(random.randint(10, 20))
        if self.running:
            self.is_auto_talking = True
            _say(random.choice(cfg.FALLBACK_TALK_TEXTS))
            time.sleep(cfg.AUTO_TALK_DURATION)
            self.root.after(0, self.hide_talk)
            self.is_auto_talking = False

        while self.running:
            delay = random.randint(self.min_auto_reply_time, self.max_auto_reply_time)
            self._sleep_chunk(delay)
            if not self.running:
                break

            # 冲突仲裁：API 正在说话则本轮跳过
            if self._api_talking:
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
        """AI 自动说话线（独立线程，仅 API 已配置时生效）"""

        def _say(text):
            try:
                self.root.after(0, lambda: self.show_talk(text))
            except Exception:
                pass

        while self.running:
            delay = random.randint(self.min_auto_reply_time, self.max_auto_reply_time)
            self._sleep_chunk(delay)
            if not self.running:
                break
            if not self.ai.is_configured:
                continue

            try:
                self._api_talking = True
                text = self.ai.auto_talk_prompt()
                _say(text)
                self.root.after(0, self.tilt_head)
                time.sleep(cfg.AUTO_TALK_DURATION)
                self.root.after(0, self.hide_talk)
            except Exception:
                pass
            finally:
                self._api_talking = False

    def _sleep_chunk(self, total_seconds):
        remaining = total_seconds
        while remaining > 0 and self.running:
            chunk = min(2, remaining)
            time.sleep(chunk)
            remaining -= chunk

    # ===================== 缩放系统 =====================
    def _show_size_menu(self):
        win = tk.Toplevel(self.root)
        win.title("调整大小")
        win.geometry("300x220")
        win.resizable(False, False)
        win.configure(bg=cfg.C_BG)
        win.transient(self.root)
        win.grab_set()
        self._center_window(win, 300, 220)

        tk.Label(win, text="调整桌宠大小",
                 font=('Microsoft YaHei', 13, 'bold'),
                 bg=cfg.C_TITLE_BG, fg=cfg.C_TITLE_FG, height=2).pack(fill='x')

        pct_label = tk.Label(win, text=f"{int(self.scale_factor * 100)}%",
                             font=('Microsoft YaHei', 22, 'bold'),
                             bg=cfg.C_BG, fg=cfg.C_ASH_DARK)
        pct_label.pack(pady=(15, 5))

        size_var = tk.DoubleVar(value=self.scale_factor)
        tk.Scale(win, from_=self.min_scale, to=self.max_scale,
                 resolution=0.1, orient='horizontal', variable=size_var,
                 font=('Microsoft YaHei', 10), bg=cfg.C_BG,
                 troughcolor=cfg.C_ASH_LIGHT, length=200,
                 showvalue=False, activebackground=cfg.C_ASH
                 ).pack(pady=10)

        def preview(*args):
            val = size_var.get()
            pct_label.config(text=f"{int(val * 100)}%")
            self._resize_pet(val)

        size_var.trace('w', preview)

        btn_frame = tk.Frame(win, bg=cfg.C_BG)
        btn_frame.pack(pady=(5, 15))
        tk.Button(btn_frame, text="重置",
                  font=('Microsoft YaHei', 10), bg=cfg.C_ROSE, fg='white',
                  relief='flat', padx=16, pady=6, activebackground=cfg.C_ROSE_DEEP,
                  command=lambda: (size_var.set(1.0), self._resize_pet(1.0),
                                   pct_label.config(text="100%"))
                  ).pack(side='left', padx=6)
        tk.Button(btn_frame, text="确定",
                  font=('Microsoft YaHei', 10, 'bold'),
                  bg=cfg.C_MINT, fg='white', relief='flat',
                  padx=16, pady=6, activebackground=cfg.C_MINT_DEEP,
                  command=win.destroy).pack(side='left', padx=6)

    def _resize_pet(self, factor):
        if factor < self.min_scale or factor > self.max_scale:
            return
        self.scale_factor = factor
        self.pet_size = (
            int(self.default_pet_size[0] * factor),
            int(self.default_pet_size[1] * factor)
        )
        self.images = self._load_images()
        self.current_img = self.images.get("stay", self._default_image())
        if self.label:
            self.label.config(image=self.current_img)
        self.root.geometry(
            f"{self.pet_size[0]}x{self.pet_size[1]}+{int(self.x)}+{int(self.y)}"
        )
        self.bubble.recalc_offsets()
        self.bubble.update_position(force=True)
        self.shake_intensity = int(3 * factor)
        self.bounce_height = int(10 * factor)

    # ===================== 设置 =====================
    def _center_window(self, win, w, h):
        win.update_idletasks()
        cx = (win.winfo_screenwidth() // 2) - (w // 2)
        cy = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{cx}+{cy}")

    def _show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("小栗帽设置")
        win.geometry("380x280")
        win.resizable(False, False)
        win.configure(bg=cfg.C_BG)
        win.transient(self.root)
        win.grab_set()
        self._center_window(win, 380, 280)

        tk.Label(win, text="⚙️  系统设置",
                 font=('Microsoft YaHei', 13, 'bold'),
                 bg=cfg.C_TITLE_BG, fg=cfg.C_TITLE_FG, height=3).pack(fill='x')

        tk.Label(win, text=f"已存消息: {self.chat_history.stats['total_messages']} 条",
                 font=('Microsoft YaHei', 10), bg=cfg.C_BG,
                 fg=cfg.C_ASH_DARK).pack(pady=(15, 10))

        min_var = tk.IntVar(value=self.min_auto_reply_time)
        max_var = tk.IntVar(value=self.max_auto_reply_time)

        frame = tk.Frame(win, bg=cfg.C_BG)
        frame.pack(pady=5)
        tk.Label(frame, text="最小间隔(秒):", font=('Microsoft YaHei', 10),
                 bg=cfg.C_BG, fg=cfg.C_TEXT).pack(side='left', padx=6)
        tk.Spinbox(frame, from_=1, to=99, textvariable=min_var,
                   font=('Microsoft YaHei', 10), width=6,
                   bg='white', fg=cfg.C_TEXT, relief='flat', bd=1
                   ).pack(side='left')
        tk.Label(frame, text="最大间隔(秒):", font=('Microsoft YaHei', 10),
                 bg=cfg.C_BG, fg=cfg.C_TEXT).pack(side='left', padx=6)
        tk.Spinbox(frame, from_=2, to=300, textvariable=max_var,
                   font=('Microsoft YaHei', 10), width=6,
                   bg='white', fg=cfg.C_TEXT, relief='flat', bd=1
                   ).pack(side='left')

        btn_frame = tk.Frame(win, bg=cfg.C_BG)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="默认",
                  font=('Microsoft YaHei', 10), bg=cfg.C_ROSE,
                  fg='white', relief='flat', padx=18, pady=8,
                  activebackground=cfg.C_ROSE_DEEP,
                  command=lambda: (min_var.set(30), max_var.set(120))
                  ).pack(side='left', padx=6)
        tk.Button(btn_frame, text="保存",
                  font=('Microsoft YaHei', 10, 'bold'),
                  bg=cfg.C_MINT, fg='white', relief='flat',
                  padx=18, pady=8, activebackground=cfg.C_MINT_DEEP,
                  command=lambda: self._save_settings(min_var.get(), max_var.get(), win)
                  ).pack(side='right', padx=6)

    def _save_settings(self, min_t, max_t, window):
        if min_t >= max_t:
            messagebox.showerror("错误", "最短间隔必须小于最长间隔！")
            return
        self.min_auto_reply_time = min_t
        self.max_auto_reply_time = max_t
        self.show_talk(cfg.SAVE_OK.format(min=min_t, max=max_t))
        self.root.after(3000, self.hide_talk)
        window.destroy()

    # ===================== API 设置 =====================
    def _show_api_settings(self):
        settings = load_api_settings()
        providers = get_provider_list()

        win = tk.Toplevel(self.root)
        win.title("API 配置")
        win.geometry("420x400")
        win.resizable(False, False)
        win.configure(bg=cfg.C_BG)
        win.transient(self.root)
        win.grab_set()
        self._center_window(win, 420, 400)

        tk.Label(win, text="大模型 API 配置",
                 font=('Microsoft YaHei', 13, 'bold'),
                 bg=cfg.C_TITLE_BG, fg=cfg.C_TITLE_FG, height=3).pack(fill='x')

        configured = bool(settings["api_key"] and len(settings["api_key"]) > 10)
        prov_info = get_provider(settings["provider"])
        prov_display = prov_info["name"] if prov_info else settings["provider"]
        status_text = f"当前: {prov_display} / {settings['model']}" if configured else "未配置"
        status_fg = cfg.C_MINT_DEEP if configured else cfg.C_ROSE_DEEP
        tk.Label(win, text=status_text, font=('Microsoft YaHei', 10),
                 bg=cfg.C_BG, fg=status_fg).pack(pady=(12, 0))

        # 厂商选择
        f1 = tk.Frame(win, bg=cfg.C_BG)
        f1.pack(fill='x', padx=30, pady=(10, 5))
        tk.Label(f1, text="厂商", font=('Microsoft YaHei', 10),
                 bg=cfg.C_BG, fg=cfg.C_ASH_DARK).pack(side='left')
        prov_var = tk.StringVar()
        prov_names = [name for _, name in providers]
        prov_keys = [key for key, _ in providers]
        current_idx = prov_keys.index(settings["provider"]) if settings["provider"] in prov_keys else 0
        prov_dd = tk.OptionMenu(f1, prov_var, *prov_names)
        prov_dd.config(font=('Microsoft YaHei', 10), bg='white', relief='flat', width=18)
        prov_dd.pack(side='left', padx=8)
        prov_var.set(prov_names[current_idx])

        # 模型选择
        f2 = tk.Frame(win, bg=cfg.C_BG)
        f2.pack(fill='x', padx=30, pady=5)
        tk.Label(f2, text="模型", font=('Microsoft YaHei', 10),
                 bg=cfg.C_BG, fg=cfg.C_ASH_DARK).pack(side='left')
        model_var = tk.StringVar()
        model_dd = tk.OptionMenu(f2, model_var, "---")
        model_dd.config(font=('Microsoft YaHei', 10), bg='white', relief='flat', width=26)
        model_dd.pack(side='left', padx=8)

        def on_provider_change(*_):
            name = prov_var.get()
            for k, n in providers:
                if n == name:
                    models = get_models(k)
                    model_var.set(settings["model"] if settings["model"] in models and k == settings["provider"]
                                  else (models[0] if models else "---"))
                    menu = model_dd["menu"]
                    menu.delete(0, "end")
                    for m in models:
                        menu.add_command(label=m, command=lambda v=m: model_var.set(v))
                    break

        prov_var.trace('w', on_provider_change)
        on_provider_change()

        # API Key
        f3 = tk.Frame(win, bg=cfg.C_BG)
        f3.pack(fill='x', padx=30, pady=5)
        tk.Label(f3, text="Key", font=('Microsoft YaHei', 10),
                 bg=cfg.C_BG, fg=cfg.C_ASH_DARK).pack(side='left')
        key_var = tk.StringVar(value=settings["api_key"])
        key_entry = tk.Entry(f3, textvariable=key_var, show="*",
                             font=('Microsoft YaHei', 10), bg='white',
                             fg=cfg.C_TEXT, relief='flat', bd=1, width=32)
        key_entry.pack(side='left', padx=8)

        key_visible = [False]
        def toggle_key():
            key_visible[0] = not key_visible[0]
            key_entry.config(show="" if key_visible[0] else "*")
            btn_toggle.config(text="🙈" if key_visible[0] else "👁")
        btn_toggle = tk.Button(f3, text="👁", font=('Microsoft YaHei', 10),
                               bg='white', relief='flat', bd=0, cursor='hand2',
                               command=toggle_key)
        btn_toggle.pack(side='left')

        # 结果提示
        result_label = tk.Label(win, text="", font=('Microsoft YaHei', 10),
                                bg=cfg.C_BG, fg=cfg.C_ASH_DARK)
        result_label.pack(pady=8)

        btn_frame = tk.Frame(win, bg=cfg.C_BG)
        btn_frame.pack(pady=10)

        def _get_provider_key():
            name = prov_var.get()
            for k, n in providers:
                if n == name:
                    return k
            return "volcengine"

        def set_buttons_state(enabled):
            for btn in [btn_test, btn_save, btn_cancel]:
                btn.config(state='normal' if enabled else 'disabled')

        def do_test():
            pk = _get_provider_key()
            k = key_var.get()
            m = model_var.get()
            if not k or len(k) < 10:
                result_label.config(text="请先填写 API Key", fg=cfg.C_ROSE_DEEP)
                return
            set_buttons_state(False)
            result_label.config(text="正在测试…", fg=cfg.C_ASH_DARK)
            def _run():
                ok, msg = test_connection(pk, k, m)
                def _update():
                    result_label.config(text=msg, fg=cfg.C_MINT_DEEP if ok else cfg.C_ROSE_DEEP)
                    set_buttons_state(True)
                self.root.after(0, _update)
            threading.Thread(target=_run, daemon=True).start()

        def do_save():
            pk = _get_provider_key()
            m = model_var.get()
            k = key_var.get()
            if not k or len(k) < 10:
                result_label.config(text="API Key 太短，请检查", fg=cfg.C_ROSE_DEEP)
                return
            save_api_settings(pk, m, k)
            self.ai.switch(pk, m, k)
            result_label.config(text="已保存 ✅", fg=cfg.C_MINT_DEEP)
            self.show_talk("API 设置已保存にゃ～✨")
            self.root.after(2000, self.hide_talk)

        btn_test = tk.Button(btn_frame, text="测试连接",
                  font=('Microsoft YaHei', 10),
                  bg=cfg.C_SKY, fg='white', relief='flat',
                  padx=14, pady=6, activebackground=cfg.C_SKY_DEEP,
                  command=do_test)
        btn_test.pack(side='left', padx=5)
        btn_save = tk.Button(btn_frame, text="保存",
                  font=('Microsoft YaHei', 10, 'bold'),
                  bg=cfg.C_MINT, fg='white', relief='flat',
                  padx=14, pady=6, activebackground=cfg.C_MINT_DEEP,
                  command=do_save)
        btn_save.pack(side='left', padx=5)
        btn_cancel = tk.Button(btn_frame, text="关闭",
                  font=('Microsoft YaHei', 10),
                  bg=cfg.C_ROSE, fg='white', relief='flat',
                  padx=14, pady=6, activebackground=cfg.C_ROSE_DEEP,
                  command=win.destroy)
        btn_cancel.pack(side='left', padx=5)

    # ===================== 聊天记录 =====================
    def _show_chat_history(self):
        if len(self.chat_history) == 0:
            self.show_talk(cfg.NO_HISTORY)
            return

        win = tk.Toplevel(self.root)
        win.title("小栗帽聊天记录")
        win.geometry("580x480")
        win.configure(bg=cfg.C_BG)
        win.transient(self.root)
        self._center_window(win, 580, 480)

        tk.Label(win, text="聊天记录",
                 font=('Microsoft YaHei', 13, 'bold'),
                 bg=cfg.C_TITLE_BG, fg=cfg.C_TITLE_FG, height=2).pack(fill='x')

        search_var = tk.StringVar()
        search_entry = tk.Entry(win, textvariable=search_var,
                                font=('Microsoft YaHei', 10),
                                bg='white', fg=cfg.C_TEXT, width=28,
                                relief='flat', bd=1)
        search_entry.pack(pady=(10, 5), padx=10, anchor='w')
        search_entry.focus()

        text_area = scrolledtext.ScrolledText(
            win, wrap=tk.WORD, font=('Microsoft YaHei', 10),
            bg=cfg.C_PANEL_BG, fg=cfg.C_TEXT, relief='flat', bd=0
        )
        text_area.pack(fill='both', expand=True, padx=10, pady=5)

        def render(filter_text=""):
            text_area.delete(1.0, tk.END)
            records = self.chat_history.search(filter_text) if filter_text else self.chat_history.history
            for msg in reversed(records[-200:]):
                role = "👤 主人" if msg["role"] == "user" else "🐱 小栗帽"
                text_area.insert(tk.END, f"{msg['timestamp']}  {role}\n{msg['content']}\n")
                text_area.insert(tk.END, "─" * 50 + "\n\n")

        search_var.trace('w', lambda *a: render(search_var.get()))
        render()

        btn_frame = tk.Frame(win, bg=cfg.C_BG)
        btn_frame.pack(fill='x', padx=10, pady=10)
        tk.Button(btn_frame, text="导出", bg=cfg.C_SKY_DEEP, fg='white',
                  font=('Microsoft YaHei', 10),
                  relief='flat', padx=14, pady=6, activebackground=cfg.C_SKY,
                  command=lambda: self._export_chat_history(win)
                  ).pack(side='left', padx=5)
        tk.Button(btn_frame, text="关闭", bg=cfg.C_ROSE, fg='white',
                  font=('Microsoft YaHei', 10),
                  relief='flat', padx=14, pady=6, activebackground=cfg.C_ROSE_DEEP,
                  command=win.destroy).pack(side='right', padx=5)
        win.bind('<Escape>', lambda e: win.destroy())

    def _export_chat_history(self, parent):
        from tkinter import filedialog
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            parent=parent, title="导出聊天记录",
            initialfile=f"chat_history_{ts}.txt",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt")]
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("小栗帽聊天记录导出\n" + "=" * 50 + "\n\n")
                for msg in self.chat_history.history:
                    role = "主人" if msg["role"] == "user" else "小栗帽"
                    f.write(f"[{msg['timestamp']}] {role}: {msg['content']}\n\n")
            self.show_talk(cfg.EXPORT_OK.format(name=os.path.basename(path)))

    def _clear_chat_history(self):
        if messagebox.askyesno("确认", "确定要清空所有聊天记录吗？"):
            self.chat_history.clear()
            self.show_talk(cfg.HISTORY_CLEARED)

    # ===================== 内存监控 =====================
    def _memory_monitor(self):
        while self.running:
            time.sleep(cfg.MEMORY_CHECK_INTERVAL)
            try:
                try:
                    import psutil
                    mem = psutil.Process(os.getpid()).memory_info().rss
                    if mem > cfg.MAX_MEMORY_USAGE:
                        gc.collect()
                        self.gc_counter += 1
                except ImportError:
                    pass
                uptime = time.time() - self.start_time
                if int(uptime) % 3600 < 60:
                    h = int(uptime // 3600)
                    m = int((uptime % 3600) // 60)
                    print(f"📊 运行: {h}h{m}m | 消息: {len(self.chat_history)} | GC: {self.gc_counter}")
            except Exception as e:
                print(f"内存监控异常: {e}")
                time.sleep(60)

    def get_system_info(self):
        info = {
            "运行时间": f"{int((time.time() - self.start_time) // 3600)}小时",
            "聊天记录": len(self.chat_history),
            "GC执行次数": self.gc_counter,
            "错误数量": len(self.error_log),
        }
        try:
            import psutil
            info["内存使用"] = f"{psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024):.1f}MB"
        except ImportError:
            info["内存使用"] = "不可用"
        return info

    # ===================== 退出 =====================
    def quit(self):
        print("正在退出程序...")
        self.running = False
        self.stop_all_animations()
        self.status.stop()
        self.chat_history.save()

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
            self.root.after(500, self.root.destroy)
        ))

    def __del__(self):
        try:
            self.running = False
            if hasattr(self, 'root') and self.root:
                self.root.destroy()
        except Exception:
            pass
