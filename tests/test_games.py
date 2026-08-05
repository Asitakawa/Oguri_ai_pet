"""四个新小游戏：规则层与注册表测试（不依赖 Tk 窗口）"""
from game.rules import (
    ONIGIRI_ITEM_TYPES,
    CatchRules,
    DashRules,
    EatingRules,
    FishingRules,
)


# ── 接饭团 ──────────────────────────────
def test_catch_would_catch():
    # 桌宠 x=100, w=180 → 中心 190，接取横向区间 [100, 280]
    assert CatchRules.would_catch(100, 180, 190, 180, 180) is True
    assert CatchRules.would_catch(100, 180, 100, 200, 180) is True
    assert CatchRules.would_catch(100, 180, 285, 200, 180) is False
    # 还没落到桌宠顶部
    assert CatchRules.would_catch(100, 180, 190, 100, 180) is False


def test_catch_pick_item_valid():
    for _ in range(200):
        item = CatchRules.pick_item()
        assert item["kind"] in ONIGIRI_ITEM_TYPES


def test_catch_score_tier():
    assert "躲着我" in CatchRules.score_tier(0)
    assert "躲着我" in CatchRules.score_tier(7)
    assert "三分饱" in CatchRules.score_tier(10)
    assert "跑一圈" in CatchRules.score_tier(14)
    assert "很满足" in CatchRules.score_tier(18)
    assert "大丰收" in CatchRules.score_tier(22)


# ── 大胃王速吃 ──────────────────────────
def test_eating_damage_and_boost():
    assert EatingRules.damage(False) == 1
    assert EatingRules.damage(True) == 2
    assert EatingRules.is_boost(5) is True
    assert EatingRules.is_boost(4) is False


def test_eating_rice_count():
    assert EatingRules.rice_count(100) == 10
    assert EatingRules.rice_count(1) == 1
    assert EatingRules.rice_count(0) == 0
    assert EatingRules.rice_count(50) == 5


def test_eating_result_tier():
    assert "嗝" in EatingRules.result_tier(0, 8)
    assert "谢谢款待" in EatingRules.result_tier(0, 3)
    assert "差一点" in EatingRules.result_tier(2, 0)
    assert "胃口" in EatingRules.result_tier(40, 0)


# ── 冲刺障碍跑 ──────────────────────────
def test_dash_vertical_physics_lands():
    y, vy, on_ground = 100.0, -15.0, False
    ground = 100.0
    steps = 0
    while not on_ground:
        y, vy, on_ground = DashRules.step_vertical(y, vy, on_ground, ground)
        steps += 1
        assert steps < 2000
    assert y == ground
    assert vy == 0.0
    assert on_ground is True


def test_dash_vertical_grounded_stays():
    y, vy, og = DashRules.step_vertical(100.0, 0.0, True, 100.0)
    assert (y, vy, og) == (100.0, 0.0, True)


def test_dash_collides():
    assert DashRules.collides(0, 0, 10, 10, 5, 5, 10, 10) is True
    assert DashRules.collides(0, 0, 10, 10, 20, 5, 10, 10) is False
    assert DashRules.collides(0, 0, 10, 10, 0, 20, 10, 10) is False


def test_dash_speed_at():
    assert DashRules.speed_at(0) == DashRules.BASE_SPEED
    assert DashRules.speed_at(10) == DashRules.BASE_SPEED + DashRules.SPEEDUP_STEP
    assert DashRules.speed_at(10 ** 9) == DashRules.MAX_SPEED


def test_dash_pick_obstacle_kinds():
    for elapsed in (0, 35, 60):
        for _ in range(80):
            assert DashRules.pick_obstacle(elapsed) in (
                "hurdle", "rock", "wall", "tree", "double", "bird")


def test_dash_bird_and_double_only_late():
    for _ in range(300):
        assert DashRules.pick_obstacle(10) not in ("bird", "double")


def test_dash_hard_recovery():
    for _ in range(100):
        assert DashRules.pick_obstacle(60, last_kind="bird") in ("hurdle", "rock")
        assert DashRules.pick_obstacle(60, last_kind="double") in ("hurdle", "rock")


def test_dash_obstacle_rects():
    one = DashRules.obstacle_rects("wall", 100, 700, 5, 180)
    assert len(one) == 1 and one[0]["h"] == 90
    low = DashRules.obstacle_rects("hurdle", 100, 700, 5, 180)
    assert low[0]["y"] == 700 - 38
    two = DashRules.obstacle_rects("double", 100, 700, 5, 180)
    assert len(two) == 2 and two[1]["x"] > two[0]["x"]
    bird = DashRules.obstacle_rects("bird", 100, 700, 5, 180)
    assert bird[0]["y"] < 700 - 180  # 飞鸟在桌宠头顶之上


def test_dash_pet_hitbox():
    x, y, w, h = DashRules.pet_hitbox(0, 0, 180, 180)
    assert w < 180 and h <= 180
    assert x > 0 and y > 0
    assert y + h == 180  # 底部对齐


def test_dash_distance_tier():
    assert "热完身" in DashRules.distance_tier(50)
    assert "更快" in DashRules.distance_tier(200)
    assert "冲刺" in DashRules.distance_tier(450)
    assert "比赛" in DashRules.distance_tier(800)
    assert "全力冲刺" in DashRules.distance_tier(5000)


# ── 钓鱼时机 ────────────────────────────
def test_fishing_zone_half():
    assert FishingRules.zone_half(1) == 60
    assert FishingRules.zone_half(3) == 60
    assert FishingRules.zone_half(4) == 45
    assert FishingRules.zone_half(6) == 45
    assert FishingRules.zone_half(7) == 30
    assert FishingRules.zone_half(10) == 30


def test_fishing_bobber_range():
    for t in (0, 1, 2, 3, 10):
        y = FishingRules.bobber_y(t, 1)
        assert FishingRules.CENTER_Y - FishingRules.AMPLITUDE - 1 <= y <= FishingRules.CENTER_Y + FishingRules.AMPLITUDE + 1
    assert abs(FishingRules.bobber_y(0, 1) - FishingRules.CENTER_Y) < 1


def test_fishing_period_at():
    assert FishingRules.period_at(1) == 4.0
    assert FishingRules.period_at(4) == 3.2
    assert FishingRules.period_at(7) == 2.6
    assert FishingRules.period_at(8) == 2.6


def test_fishing_judge():
    assert FishingRules.judge(0, 60) == "perfect"
    assert FishingRules.judge(60, 60) == "perfect"
    assert FishingRules.judge(70, 60) == "near"
    assert FishingRules.judge(80, 60) == "near"
    assert FishingRules.judge(81, 60) == "miss"
    assert FishingRules.judge(100, 60) == "miss"


def test_fishing_reward():
    assert FishingRules.reward("miss") == ("", 0)
    _, val = FishingRules.reward("near")
    assert val == 1
    _, val = FishingRules.reward("perfect")
    assert val in (2, 3)


def test_fishing_result_tier():
    assert "睡觉" in FishingRules.result_tier(3)
    assert "晚餐" in FishingRules.result_tier(8)
    assert "满载" in FishingRules.result_tier(12)
    assert "冠军" in FishingRules.result_tier(16)


# ── 注册表 ──────────────────────────────
def test_registry_contains_new_games():
    from game import GAMES

    for key in ("onigiri_catch", "eating_rush", "dash_run", "fishing"):
        assert key in GAMES
        assert GAMES[key]["name"]
        assert GAMES[key]["cls"] is not None
