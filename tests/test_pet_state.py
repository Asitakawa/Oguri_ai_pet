"""饱腹/活力状态机数值逻辑

注意：PetStatus 现在会从数据目录读写 pet_state.json，测试必须传自己的临时路径，
否则会读到（并污染）开发者本机的真实状态。
"""
import pytest

from core import config as cfg
from core.pet_state import PetStatus


@pytest.fixture
def status(tmp_path):
    """干净、不落真实数据的 PetStatus。"""
    s = PetStatus(str(tmp_path / "pet_state.json"), autostart=False)
    yield s
    s.stop()


def test_initial_values(status):
    assert status.hunger == cfg.HUNGER_MAX
    assert status.energy == cfg.ENERGY_MAX
    assert status.hunger_pct == 100
    assert status.energy_pct == 100


def test_feed_and_spend(status):
    status.spend_energy()
    assert status.energy == cfg.ENERGY_MAX - cfg.INTERACT_ENERGY_COST
    status.feed()
    assert status.hunger == cfg.HUNGER_MAX
    assert status.energy == cfg.ENERGY_MAX  # 回满并封顶


def test_energy_never_negative(status):
    for _ in range(cfg.ENERGY_MAX + 50):
        status.spend_energy()
    assert status.energy == 0


def test_low_energy_callback(status):
    calls = []
    status._on_energy_low = lambda: calls.append(1)
    status.energy = cfg.ENERGY_LOW_THRESHOLD - 1
    status._on_energy_low()
    assert calls == [1]


def test_low_state_notified_once_not_every_tick(status):
    """低值只是一次状态跃迁：持续低于阈值时不应每轮循环都提醒。"""
    t = 1000.0
    assert status._should_notify("_hunger_low", 29.0, 30.0, t) is True
    # 之后连续多轮仍是低值 → 不重复提醒
    for i in range(1, 20):
        assert status._should_notify("_hunger_low", 29.0, 30.0, t + i) is False


def test_low_state_rearms_after_recovery(status):
    """恢复到阈值+回差以上后重新武装，再次掉下去要能提醒。"""
    t = 1000.0
    assert status._should_notify("_hunger_low", 29.0, 30.0, t) is True
    # 仅回到阈值上方但不足回差 → 仍视为低值区，不重新武装
    assert status._should_notify("_hunger_low", 35.0, 30.0, t + 1) is False
    assert status._should_notify("_hunger_low", 29.0, 30.0, t + 2) is False
    # 超过阈值+回差 → 解除低值态
    assert status._should_notify("_hunger_low", 41.0, 30.0, t + 3) is False
    assert status._should_notify("_hunger_low", 29.0, 30.0, t + 4) is True


def test_low_state_repeats_after_cooldown(status):
    """长时间不处理时，按冷却间隔再提醒一次。"""
    t = 1000.0
    assert status._should_notify("_hunger_low", 10.0, 30.0, t) is True
    assert status._should_notify("_hunger_low", 10.0, 30.0, t + 60) is False
    later = t + cfg.LOW_STATE_REPEAT_INTERVAL + 1
    assert status._should_notify("_hunger_low", 10.0, 30.0, later) is True
