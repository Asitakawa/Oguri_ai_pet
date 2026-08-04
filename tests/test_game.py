"""小游戏：一飞冲天高度分档"""
from game.fly_high.game import FlyHighGame


def test_replies_tiers():
    # PX_PER_METER = 100，因此 4000px = 40m < 50m → 第一档
    first = FlyHighGame.replies_for_height(4000)
    assert "变重" in first[0] or "没吃饱" in first[0]

    second = FlyHighGame.replies_for_height(15000)  # 150m
    assert "热身" in second[1] or "高了一点" in second[0]

    third = FlyHighGame.replies_for_height(30000)  # 300m
    assert "冲刺" in third[0] or "飞起来" in third[0]

    fourth = FlyHighGame.replies_for_height(45000)  # 450m
    assert "哇啊" in fourth[0]

    fifth = FlyHighGame.replies_for_height(60000)  # 600m
    assert "云" in fifth[0] or "吃不下" in fifth[1]
