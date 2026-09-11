"""小游戏：一飞冲天高度分档

PX_PER_METER = 10.0，因此 400px = 40 米。档位边界见 FlyHighGame.LAND_TIERS。
"""
from game.fly_high.game import FlyHighGame


def test_replies_tiers():
    first = FlyHighGame.replies_for_height(400)  # 40m < 50m
    assert "变重" in first[0] or "没吃饱" in first[0]

    second = FlyHighGame.replies_for_height(1500)  # 150m
    assert "热身" in second[1] or "高了一点" in second[0]

    third = FlyHighGame.replies_for_height(3000)  # 300m
    assert "冲刺" in third[0] or "飞起来" in third[0]

    fourth = FlyHighGame.replies_for_height(4500)  # 450m
    assert "哇啊" in fourth[0]

    fifth = FlyHighGame.replies_for_height(6000)  # 600m
    assert "云" in fifth[0] or "吃不下" in fifth[1]


def test_tier_boundaries():
    """档位边界应严格按换算后的米数切分。"""
    assert FlyHighGame.replies_for_height(499) == FlyHighGame.LAND_TIERS[0][1]   # 49.9m
    assert FlyHighGame.replies_for_height(500) == FlyHighGame.LAND_TIERS[1][1]   # 50.0m
    assert FlyHighGame.replies_for_height(1999) == FlyHighGame.LAND_TIERS[1][1]  # 199.9m
    assert FlyHighGame.replies_for_height(2000) == FlyHighGame.LAND_TIERS[2][1]  # 200m


def test_px_per_meter_matches_other_games():
    """单位不应与其他游戏漂移（曾出现 100 vs 10 的不一致）。"""
    from game.rules import DashRules

    assert FlyHighGame.PX_PER_METER == DashRules.PX_PER_METER


def test_first_tiers_reachable_on_a_normal_screen():
    """屏幕内一次普通甩动就应能进入前两档，否则档位形同虚设。

    用能量守恒估算峰值：h = v² / (2g)（v 为 px/帧，g 为 px/帧²）。
    """
    g = FlyHighGame.GRAVITY
    screen_h = 1080
    # 一次「甩得比较用力」的脱手速度：30 px/帧（20ms 一帧 → 1500 px/s）
    peak_px = 30.0 ** 2 / (2 * g)
    peak_m = peak_px / FlyHighGame.PX_PER_METER
    assert peak_m > 50, f"峰值仅 {peak_m:.0f}m，第一档都够不到"
    assert peak_m < screen_h / FlyHighGame.PX_PER_METER * 10  # 量级合理
