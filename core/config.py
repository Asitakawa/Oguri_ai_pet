"""全局配置常量"""

DEFAULT_PET_SIZE = (180, 180)
MIN_SCALE = 0.5
MAX_SCALE = 2.0

DEFAULT_MIN_AUTO_REPLY = 60
DEFAULT_MAX_AUTO_REPLY = 300
MIN_AUTO_REPLY = DEFAULT_MIN_AUTO_REPLY
MAX_AUTO_REPLY = DEFAULT_MAX_AUTO_REPLY
PRESET_MIN_INTERVAL = 120
PRESET_MAX_INTERVAL = 600
AUTO_TALK_DURATION = 5

SHAKE_INTENSITY = 3
BOUNCE_HEIGHT = 10
INERTIA_FRICTION = 0.85

DEFAULT_MODEL = "doubao-seed-1-6-vision-250815"
API_SETTINGS_FILE = ".env"
API_PROVIDER_KEY = "AI_PROVIDER"
API_MODEL_KEY = "AI_MODEL"
API_KEY_KEY = "API_KEY"

CHAT_HISTORY_FILE = "chat_history.json"
MAX_HISTORY_LENGTH = 2000
MEMORY_CONTEXT_SIZE = 400

DATA_LOCK_FILE = ".pet.lock"
MEMORY_CHECK_INTERVAL = 180
MAX_MEMORY_USAGE = 800 * 1024 * 1024
ERROR_LOG_MAX = 100

BUBBLE_BASE_WIDTH = 240
BUBBLE_BASE_HEIGHT = 96
INPUT_BOX_WIDTH = 380
INPUT_BOX_HEIGHT = 56

# 小栗帽主题色
C_SNOW = "#faf8f5"
C_CREAM = "#f3ede5"
C_ASH = "#b8c0cc"
C_ASH_DARK = "#8893a0"
C_ASH_LIGHT = "#d4dae2"
C_WOOD = "#8b7355"
C_WOOD_LIGHT = "#c4a882"
C_ROSE = "#e8c8c0"
C_ROSE_DEEP = "#d4a99a"
C_MINT = "#bdd6c8"
C_MINT_DEEP = "#9bc0ae"
C_SKY = "#b8cfe0"
C_SKY_DEEP = "#94b4cc"

C_BG = C_SNOW
C_TITLE_BG = "#92a0b4"
C_TITLE_FG = "#ffffff"
C_PANEL_BG = C_CREAM
C_TEXT = C_WOOD
C_ACCENT = C_ASH_DARK
C_BTN_OK = C_MINT
C_BTN_OK_HOVER = C_MINT_DEEP
C_BTN_WARN = C_ROSE
C_BTN_WARN_HOVER = C_ROSE_DEEP
C_BTN_PRIMARY = C_SKY
C_BTN_PRIMARY_HOVER = C_SKY_DEEP
C_BUBBLE_BG = "#fffefb"
C_BUBBLE_OUTLINE = C_ASH_LIGHT
C_BUBBLE_TEXT = C_WOOD
C_INPUT_BG = "#f7f4ef"

SYSTEM_PROMPT = (
    "你是赛马娘小栗帽，天然呆、元气满满、爱吃美食的大胃王，"
    "说话可爱活泼，灰发灰蓝瞳的芦毛马娘，有呆毛和分叉长发，"
    "性格温柔但有点天然，回答简洁可爱（10-20字）。"
)

FALLBACK_TALK_TEXTS = [
    "肚子饿了にゃ～有没有饭团🍙",
    "今天也要努力跑一圈！",
    "呼～稍微休息一下也没关系吧…",
    "训练员训练员，小栗帽在这里哦～",
    "灰蓝色的毛茸茸，想被摸摸头にゃ✨",
    "诶？刚才在想什么呢…忘记啦！",
    "饭团真好吃～再多也吃得下！",
    "和小玉酱一起跑的话会更快哦～",
]

FALLBACK_AI_RESPONSES = [
    "うーん…这个问题好难にゃ～",
    "训练员说得对呢✨小栗帽也这么想！",
    "诶诶？脑袋转不过来了啦～",
    "虽然不太懂，但听起来好厉害🌟",
]

FALLBACK_SCREENSHOT_RESPONSES = [
    "哇～屏幕上有好多东西にゃ！",
    "这个画面让肚子更饿了…🍙",
    "让小栗帽仔细看看～嗯…嗯…",
    "好像藏着什么好吃的东西！",
    "信息太多啦，脑袋冒烟了～💨",
    "画面好精彩！小栗帽也想加入✨",
]

CLICK_RESPONSES = [
    "啊呜～被戳到了にゃ！",
    "痒痒的～训练员的手指好温柔✨",
    "戳一下就想吃一个饭团🍙",
    "再戳的话…栗帽会忍不住撒娇哦～",
]

SPECIAL_CLICK_RESPONSES = [
    "わわっ！连击太快啦にゃ～💦",
    "训练员太厉害了，小栗帽眼花缭乱✨",
    "这样下去训练都不用做了啦～",
    "停、停不下来～要飞起来了🌟",
]

FIRST_CLICK = "あっ！被训练员戳到了にゃ～✨"
FIRST_SPECIAL_CLICK = "连击好厉害！小栗帽要加油跟上🌟"
SCREENSHOT_START = "栗帽看看训练员在做什么～"
SCREENSHOT_LOADING = "正在看看屏幕にゃ📸"
SCREENSHOT_FAIL = "呜…看不到屏幕了😢"
SCREENSHOT_ERROR = "あれ？脑袋冒烟了💨"
INPUT_EMPTY = "训练员想说什么にゃ？"
INPUT_THINKING = "让小栗帽想想…"
INPUT_SCREENSHOT_THINKING = "边看屏幕边想…"
LOADING_DANCE = "✨ 要跳舞啦 ✨"
NO_HISTORY = "还没有聊天记录にゃ～"
HISTORY_CLEARED = "记录清空啦～小栗帽会记住训练员的🗑️"
SAVE_OK = "保存成功にゃ～！{min}-{max}秒✨"
EXPORT_OK = "已导出到:\n{name}にゃ～✨"

GOODBYE_MESSAGES = [
    "训练员和小栗帽一起过了{hrs}小时{mins}分钟にゃ～下次也要一起玩ね✨",
    "聊了{msgs}条消息！栗帽好开心～要记得喂饭团哦👋",
    "小栗帽去找小玉酱跑步啦～下次再见にゃ～🌟",
    "今天也很开心！小栗帽在赛场等训练员来看ね🍙",
]

# 状态系统
HUNGER_MAX = 100
ENERGY_MAX = 100
HUNGER_DECAY_PER_MIN = 2
ENERGY_REGEN_PER_MIN = 1
FEED_HUNGER_BOOST = 30
FEED_ENERGY_BOOST = 5
INTERACT_ENERGY_COST = 1
HUNGER_LOW_THRESHOLD = 30
ENERGY_LOW_THRESHOLD = 25
# 字体设置
FONT_FAMILY = "Microsoft YaHei"
FONT_SIZE = 11
FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 24

STATUS_BAR_WIDTH = 200
STATUS_BAR_HEIGHT = 36
STATUS_UPDATE_INTERVAL = 10

FEED_TALK_TEXTS = [
    "もぐもぐ…饭团好好吃にゃ🍙",
    "啊～谢谢训练员的饭团✨",
    "肚子满满的，好幸福～",
    "饱了饱了！小栗帽又有力气啦！",
]

HUNGRY_TALK_TEXTS = [
    "肚子咕咕叫了にゃ…🍙",
    "唔…有点饿了…",
    "训练员，饭团时间到了吗？",
]

TIRED_TALK_TEXTS = [
    "呼にゃ…有点困了…",
    "稍微闭上眼一下下…💤",
    "今晚想早点休息呢～",
]

# ── 持久化设置 ──────────────────────────────
import json
from utils.paths import get_data_path

_SETTINGS_FILE = get_data_path("settings.json")


def _save():
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "font_family": FONT_FAMILY,
                "font_size": FONT_SIZE,
                "memory_context_size": MEMORY_CONTEXT_SIZE,
                "min_auto_reply": MIN_AUTO_REPLY,
                "max_auto_reply": MAX_AUTO_REPLY,
                "auto_talk_duration": AUTO_TALK_DURATION,
                "preset_min_interval": PRESET_MIN_INTERVAL,
                "preset_max_interval": PRESET_MAX_INTERVAL,
            }, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"设置保存失败: {e}")


def _load():
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
            for k, v in [("font_family", "FONT_FAMILY"), ("font_size", "FONT_SIZE"),
                         ("memory_context_size", "MEMORY_CONTEXT_SIZE"),
                         ("min_auto_reply", "MIN_AUTO_REPLY"),
                         ("max_auto_reply", "MAX_AUTO_REPLY"),
                         ("auto_talk_duration", "AUTO_TALK_DURATION"),
                         ("preset_min_interval", "PRESET_MIN_INTERVAL"),
                         ("preset_max_interval", "PRESET_MAX_INTERVAL")]:
                if k in d:
                    globals()[v] = d[k]
    except Exception:
        pass


_load()
