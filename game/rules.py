"""小游戏纯规则层 — 不依赖 Tk，便于单元测试与复用"""
from __future__ import annotations

import math
import random
from typing import Dict

# ── 接饭团 ──────────────────────────────
ONIGIRI_ITEM_TYPES: Dict[str, dict] = {
    "onigiri": {"emoji": "🍙", "value": 1, "weight": 60, "speed": 1.0, "drift": 0.0},
    "sushi":   {"emoji": "🍣", "value": 3, "weight": 12, "speed": 1.4, "drift": 1.0},
    "carrot":  {"emoji": "🥕", "value": 1, "weight": 10, "speed": 1.0, "drift": 0.0},
    "star":    {"emoji": "⭐", "value": 2, "weight": 8,  "speed": 1.1, "drift": 0.5},
    "bad":     {"emoji": "💢", "value": -2, "weight": 10, "speed": 1.0, "drift": 0.0},
}


class CatchRules:
    """接饭团：掉落物生成、接取判定、得分分档。"""

    BASE_VY = 6.0         # px/帧（33ms ≈ 180px/s）
    BASE_INTERVAL = 1.2   # 秒
    MIN_INTERVAL = 0.5
    MAX_ITEMS = 5
    SPEEDUP_EVERY = 15    # 秒
    SPEEDUP_FACTOR = 1.1

    @staticmethod
    def pick_item() -> dict:
        total = sum(t["weight"] for t in ONIGIRI_ITEM_TYPES.values())
        r = random.uniform(0, total)
        acc = 0.0
        for key, t in ONIGIRI_ITEM_TYPES.items():
            acc += t["weight"]
            if r <= acc:
                return dict(t, kind=key)
        return dict(ONIGIRI_ITEM_TYPES["onigiri"], kind="onigiri")

    @staticmethod
    def would_catch(pet_x: float, pet_w: float,
                    item_x: float, item_y: float, pet_y: float) -> bool:
        """掉落物中心是否进入桌宠顶部接取范围。"""
        center = pet_x + pet_w / 2
        return item_y >= pet_y - 8 and abs(item_x - center) <= pet_w / 2

    @staticmethod
    def score_tier(score: int) -> str:
        if score < 20:
            return "今天的饭团…都在躲着我"
        if score < 40:
            return "肚子只有三分饱"
        if score < 60:
            return "刚刚好，还能再跑一圈"
        if score < 80:
            return "吃得很满足了！"
        return "大丰收！今晚不用做饭了！"


# ── 大胃王速吃 ──────────────────────────
class EatingRules:
    """大胃王速吃：饭量、点击频率、暴食、分档。"""

    TOTAL_FOOD = 100
    TIME_LIMIT = 20.0
    MAX_RATE = 8.0     # 每秒最大有效点击（反宏）
    BOOST_RATE = 5.0   # 触发暴食的每秒点击数
    NORMAL_DAMAGE = 1
    BOOST_DAMAGE = 2
    SLOTS = 10

    @staticmethod
    def damage(boost: bool) -> int:
        return EatingRules.BOOST_DAMAGE if boost else EatingRules.NORMAL_DAMAGE

    @staticmethod
    def is_boost(clicks_in_last_second: int) -> bool:
        return clicks_in_last_second >= EatingRules.BOOST_RATE

    @staticmethod
    def rice_count(food_left: int) -> int:
        return max(0, math.ceil(food_left / (EatingRules.TOTAL_FOOD / EatingRules.SLOTS)))

    @staticmethod
    def result_tier(food_left: int, time_left: float) -> str:
        if food_left <= 0:
            return "谢谢款待！训练员辛苦了！" if time_left <= 5 else "嗝～好满足！还能再战一碗！"
        if food_left <= 3:
            return "唔…差一点点就吃完了"
        if food_left <= 20:
            return "还剩一点…肚子还能再塞"
        return "今天胃口好像不太好…"


# ── 冲刺障碍跑 ──────────────────────────
class DashRules:
    """冲刺障碍跑：垂直物理、碰撞、障碍生成、分档。"""

    JUMP_V = -15.0
    GRAVITY = 0.8
    BASE_SPEED = 5.0        # px/帧
    MAX_SPEED = 11.0
    SPEEDUP_EVERY = 10.0    # 秒
    SPEEDUP_STEP = 0.5
    PX_PER_METER = 10.0
    SPAWN_MIN_FRAMES = 55
    SPAWN_MAX_FRAMES = 110

    @staticmethod
    def step_vertical(pet_y: float, vy: float, on_ground: bool, ground_y: float):
        """一帧垂直物理：返回 (pet_y, vy, on_ground)。"""
        if on_ground:
            return pet_y, vy, True
        vy += DashRules.GRAVITY
        pet_y += vy
        if pet_y >= ground_y:
            pet_y = ground_y
            vy = 0.0
            on_ground = True
        return pet_y, vy, on_ground

    @staticmethod
    def collides(px: float, py: float, pw: float, ph: float,
                 ox: float, oy: float, ow: float, oh: float) -> bool:
        """AABB 碰撞检测。"""
        return not (px + pw <= ox or ox + ow <= px or py + ph <= oy or oy + oh <= py)

    @staticmethod
    def speed_at(elapsed: float) -> float:
        return min(DashRules.MAX_SPEED,
                   DashRules.BASE_SPEED + DashRules.SPEEDUP_STEP * int(elapsed // DashRules.SPEEDUP_EVERY))

    @staticmethod
    def pick_obstacle(elapsed: float) -> str:
        r = random.random()
        if elapsed >= 45:
            if r < 0.40:
                return "low"
            if r < 0.60:
                return "high"
            if r < 0.80:
                return "double"
            return "flyer"
        if elapsed >= 30:
            if r < 0.50:
                return "low"
            if r < 0.75:
                return "high"
            return "double"
        return "low" if r < 0.60 else "high"

    @staticmethod
    def distance_tier(meters: float) -> str:
        if meters < 100:
            return "还没热完身…"
        if meters < 300:
            return "还行，下次更快！"
        if meters < 600:
            return "有冲刺的感觉了！"
        if meters < 1000:
            return "像比赛一样兴奋！"
        return "这是…我的全力冲刺！"


# ── 钓鱼时机 ────────────────────────────
class FishingRules:
    """钓鱼时机：浮标运动、区间收窄、判定、奖励。"""

    TOTAL_ROUNDS = 10
    ROUND_SECONDS = 8.0
    RESULT_SECONDS = 2.0
    AMPLITUDE = 150.0
    PERIOD = 4.0
    CENTER_Y = 260.0

    @staticmethod
    def zone_half(round_no: int) -> float:
        if round_no <= 3:
            return 60.0
        if round_no <= 6:
            return 45.0
        return 30.0

    @staticmethod
    def bobber_y(elapsed: float) -> float:
        return (FishingRules.CENTER_Y
                + FishingRules.AMPLITUDE * math.sin(2 * math.pi * elapsed / FishingRules.PERIOD))

    @staticmethod
    def judge(offset: float, zone_half: float) -> str:
        abs_off = abs(offset)
        if abs_off <= zone_half:
            return "perfect"
        if abs_off <= zone_half + 20:
            return "near"
        return "miss"

    @staticmethod
    def reward(judgment: str):
        if judgment == "perfect":
            return random.choice([("🐠", 2), ("🦐", 3)])
        if judgment == "near":
            return ("🐟", 1)
        return ("", 0)

    @staticmethod
    def result_tier(points: int) -> str:
        if points <= 5:
            return "今天的鱼都在睡觉"
        if points <= 12:
            return "晚餐有着落了！"
        if points <= 18:
            return "满载而归！今晚吃鱼！"
        return "这是钓鱼冠军吧！"
