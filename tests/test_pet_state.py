"""饱腹/活力状态机数值逻辑"""
from core import config as cfg
from core.pet_state import PetStatus


def test_initial_values():
    s = PetStatus()
    try:
        assert s.hunger == cfg.HUNGER_MAX
        assert s.energy == cfg.ENERGY_MAX
        assert s.hunger_pct == 100
        assert s.energy_pct == 100
    finally:
        s.stop()


def test_feed_and_spend():
    s = PetStatus()
    try:
        s.spend_energy()
        assert s.energy == cfg.ENERGY_MAX - cfg.INTERACT_ENERGY_COST
        s.feed()
        assert s.hunger == cfg.HUNGER_MAX
        assert s.energy == cfg.ENERGY_MAX  # 回满并封顶
    finally:
        s.stop()


def test_low_energy_callback():
    calls = []
    s = PetStatus()
    s._on_energy_low = lambda: calls.append(1)
    s.energy = cfg.ENERGY_LOW_THRESHOLD - 1
    s._on_energy_low()
    assert calls == [1]
    s.stop()
