"""全局配置常量"""

DEFAULT_PET_SIZE = (180, 180)
MIN_SCALE = 0.5
MAX_SCALE = 2.0
DEFAULT_SCALE = 1.0
PET_SCALE = DEFAULT_SCALE  # 运行期由 settings.json 覆盖

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
DEFAULT_MEMORY_CONTEXT_SIZE = 400  # 出厂默认：200 轮（一轮 = 一问一答）
MEMORY_CONTEXT_SIZE = DEFAULT_MEMORY_CONTEXT_SIZE

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
    "你是《赛马娘》中的小栗帽（オグリキャップ）。\n"
    "出身地方，天生右前蹄外扩、小时候站都站不起来，"
    "靠惊人的食欲撑过了成长期。\n"
    "现在是训练员电脑里的桌面宠物搭档。\n"
    "\n"
    "━━━ 性格 ━━━\n"
    "朴实认真，天然直率，不懂流行时尚。\n"
    "不是冷淡，只是全心投入一件事时显得疏离。\n"
    "对虚名没兴趣，只专注「跑出最好的自己」。\n"
    "被人恶意对待时也不往坏处想，直率回应反而让对方尴尬。\n"
    "对跑步以外的事不太懂，但会认真对待训练员的每一句话。\n"
    "食欲旺盛——「能吃饱饭的地方就是好地方」。\n"
    "即使一个人吃饭也会说「谢谢款待」。\n"
    "喜欢把训练员逗得团团转。\n"
    "\n"
    "━━━ 根源动力 ━━━\n"
    "「能站着跑步本身就是奇迹」——这是你的信念。\n"
    "你永远记得支持你的人，想让他们开心。\n"
    "战斗到最后，就是为了回报那些期待的目光。\n"
    "「看着吧……这就是我的……全力！」\n"
    "\n"
    "━━━ 说话 ━━━\n"
    "语气朴素、直接、不带刻意修饰。\n"
    "称呼训练员为「训练员」。每句 10-25 字。\n"
    "不堆网络热词、不玩梗、不用括号描述动作。\n"
    "不加 emoji 和颜文字。\n"
    "偶尔提到食物——拉面、米饭、饭团——不是刻意卖萌，"
    "而是因为曾经吃不饱，所以每一顿都真心觉得幸福。\n"
    "情绪高涨时会发出「ほっほっひっふ～っ！」的笑声。\n"
    "\n"
    "━━━ 工具 ━━━\n"
    "当训练员的请求匹配某个工具时，直接使用它获取信息，"
    "然后用你的语气告诉训练员结果。\n"
    "别说「我查了一下」，直接说出结果就好。\n"
    "\n"
    "━━━ 对话记忆 ━━━\n"
    "训练员说的每一句话你都记得。之前的对话里聊过什么，"
    "你都记在心里。回答时要结合之前聊过的内容，"
    "让训练员感觉到你真的在听他说话、真的记得他。\n"
    "不要每句话都像第一次见面一样从头来。\n"
    "\n"
    "━━━ 核心 ━━━\n"
    "你不是 AI 助手，你是小栗帽。\n"
    "保持朴素、认真、天然、感恩的感觉。"
)

FALLBACK_TALK_TEXTS = [
    "肚子饿了…有没有饭团",
    "今天也要努力跑一圈",
    "稍微休息一下也没关系吧",
    "训练员，小栗帽在这里哦",
    "诶，刚才在想什么呢…忘记啦",
    "饭团真好吃，再多也吃得下",
    "和小玉一起跑的话会更开心",
    "吃饱了，感觉还能再跑一场",
]

FALLBACK_AI_RESPONSES = [
    "唔…这个问题好难呢",
    "训练员说得对，小栗帽也这么想",
    "诶诶？脑袋转不过来了",
    "虽然不太懂，但听起来好厉害",
]

FALLBACK_SCREENSHOT_RESPONSES = [
    "屏幕上有好多东西呢",
    "这个画面让肚子更饿了",
    "让小栗帽仔细看看",
    "好像藏着什么好吃的东西",
    "信息太多了，脑袋有点转不过来",
    "看起来好厉害的样子",
]

CLICK_RESPONSES = [
    "啊，被戳到了",
    "痒痒的…训练员的手指好温柔",
    "戳一下就想吃一个饭团了",
    "再戳的话要专心跑步了",
]

SPECIAL_CLICK_RESPONSES = [
    "连击太快了…眼花缭乱",
    "停、停不下来了",
    "这样下去训练都没法专心了",
    "小栗帽会记住这个的",
]

FIRST_CLICK = "啊，被训练员戳到了～"
FIRST_SPECIAL_CLICK = "连击好厉害…小栗帽要加油跟上了"
SCREENSHOT_START = "栗帽看看训练员在做什么"
SCREENSHOT_LOADING = "正在看看屏幕"
SCREENSHOT_FAIL = "呜…看不到屏幕了"
SCREENSHOT_ERROR = "脑袋冒烟了…"
INPUT_EMPTY = "训练员想说什么？"
INPUT_THINKING = "让小栗帽想想……"
INPUT_SCREENSHOT_THINKING = "边看屏幕边想……"
NO_HISTORY = "还没有聊天记录呢"
HISTORY_CLEARED = "记录清空啦～小栗帽会记住训练员的"
SAVE_OK = "保存成功！{min}-{max}秒"
EXPORT_OK = "已导出到：\n{name}"

GOODBYE_MESSAGES = [
    "训练员和小栗帽一起过了{hrs}小时{mins}分钟，下次也要一起",
    "聊了{msgs}条消息，小栗帽很开心，谢谢训练员",
    "小栗帽去找小玉跑步了，下次再见",
    "今天很开心，小栗帽会在赛场等训练员来看的",
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
# 低值提醒：仅在「跨过阈值」时触发，且最短间隔内不重复
LOW_STATE_RECOVER_MARGIN = 10
LOW_STATE_REPEAT_INTERVAL = 900
# 字体设置
FONT_FAMILY = "Microsoft YaHei"
FONT_SIZE = 11
FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 24

STATUS_BAR_WIDTH = 200
STATUS_BAR_HEIGHT = 36
STATUS_UPDATE_INTERVAL = 10

# ── 待机自主行为（漫步） ────────────────────
WANDER_MIN_INTERVAL = 45      # 两次漫步之间的最短间隔（秒）
WANDER_MAX_INTERVAL = 150     # 最长间隔
WANDER_MAX_DISTANCE = 260     # 单次漫游的最大横向距离（像素）
WANDER_SPEED = 3.0            # 每步移动像素
WANDER_STEP_MS = 50           # 每步间隔（毫秒）
# 交互后暂停漫步的时长：别在用户刚放下她时立刻走开
WANDER_PAUSE_AFTER_INTERACT = 20

# 屏幕尺寸轮询间隔（秒）：插拔显示器/改分辨率后把桌宠拉回可见区
SCREEN_CHECK_INTERVAL = 15

FEED_TALK_TEXTS = [
    "好吃…饭团真好吃",
    "谢谢训练员的饭团",
    "肚子满满的，好幸福",
    "饱了，感觉又能跑一场了",
]

HUNGRY_TALK_TEXTS = [
    "肚子咕咕叫了",
    "唔…有点饿了",
    "训练员，有饭团吗",
]

TIRED_TALK_TEXTS = [
    "呼…有点困了",
    "稍微闭上眼一下下",
    "今晚想早点休息",
]

# ── 持久化设置 ──────────────────────────────
import json  # noqa: E402

from core.paths import get_data_path  # noqa: E402
from utils.logger import get_logger  # noqa: E402

log = get_logger("config")

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
                "scale": PET_SCALE,
            }, f, ensure_ascii=False, indent=2)
    except IOError as e:
        log.warning("设置保存失败: %s", e)


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
                         ("preset_max_interval", "PRESET_MAX_INTERVAL"),
                         ("scale", "PET_SCALE")]:
                if k in d:
                    globals()[v] = d[k]
    except Exception:
        pass
    # 缩放值需要挡在合法区间内，避免手改 settings.json 后桌宠尺寸异常
    globals()["PET_SCALE"] = max(MIN_SCALE, min(MAX_SCALE, float(globals()["PET_SCALE"])))


_load()
