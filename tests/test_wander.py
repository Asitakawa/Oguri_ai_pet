"""待机漫步：位移上限、越界防护、游戏/交互抑制

直接复用 KurumiPet 上的真实方法（用迷你宿主对象），不建 Tk 窗口。
"""
from __future__ import annotations

import random
import time

import pytest

from core import config as cfg
from ui.pet_window import KurumiPet


class FakeRoot:
    """记录 after 回调，由测试手动推进。"""

    def __init__(self) -> None:
        self.q: list = []

    def after(self, ms, fn=None, *args):
        self.q.append((ms, fn, args))
        return f"id{len(self.q)}"

    def after_cancel(self, _i):
        pass

    def drain(self, limit: int = 200000) -> int:
        n = 0
        while self.q and n < limit:
            _ms, fn, args = self.q.pop(0)
            if fn:
                fn(*args)
            n += 1
        return n

    def drain_steps(self, steps: int) -> int:
        """只消费指定数量的已排队回调。

        漫步结束后会立刻排下一次，所以不能用 drain() 跑到底——
        那会连续走完好几轮，把位移累加起来。
        """
        n = 0
        for _ in range(steps):
            if not self.q:
                break
            _ms, fn, args = self.q.pop(0)
            if fn:
                fn(*args)
            n += 1
        return n


class MiniPet:
    """只装漫步所需字段的迷你桌宠，方法体直接用 KurumiPet 的真实实现。"""

    _start_wander_loop = KurumiPet._start_wander_loop
    _pause_wander = KurumiPet._pause_wander
    _schedule_wander = KurumiPet._schedule_wander
    _wander_allowed = KurumiPet._wander_allowed
    _begin_wander = KurumiPet._begin_wander
    _wander_step = KurumiPet._wander_step
    _busy_with_game = KurumiPet._busy_with_game

    def __init__(self, game_active: bool = False) -> None:
        self.root = FakeRoot()
        self.running = True
        self.is_dragging = False
        self.inertia_active = False
        self.is_auto_talking = False
        self._api_talking = False
        self._is_processing = False
        self.is_dialog_showing = False
        self.is_hovering = False
        self.game_manager = type("GM", (), {"is_active": lambda _s: game_active})()
        self.x = 500.0
        self.y = 300.0
        self.screen_w = 1920
        self.screen_h = 1080
        self.pet_size = (180, 180)
        self._wander_after_id = None
        self._wander_target_x = None
        self._wander_pause_until = 0.0
        self.moves = 0

    def _move(self):
        self.moves += 1

    def drain_walk(self, limit: int = 100000) -> int:
        """推进到本次漫步走完（走完会重新排程下一次，以此为止）。"""
        n = 0
        while self._wander_target_x is not None and self.root.q and n < limit:
            _ms, fn, args = self.root.q.pop(0)
            if fn:
                fn(*args)
            n += 1
        return n


@pytest.fixture(autouse=True)
def _fast_wander(monkeypatch):
    monkeypatch.setattr(cfg, "WANDER_STEP_MS", 1)


def test_single_wander_stays_within_distance_cap():
    random.seed(1234)
    deltas = []
    for _ in range(40):
        p = MiniPet()
        start = p.x
        p._begin_wander()
        p.drain_walk()
        deltas.append(abs(p.x - start))
    assert min(deltas) > 0, "应该真的走动"
    assert max(deltas) <= cfg.WANDER_MAX_DISTANCE + 1, (
        f"单次漫游位移 {max(deltas):.0f}px 超过上限 {cfg.WANDER_MAX_DISTANCE}px"
    )


def test_wander_reaches_its_target():
    random.seed(555)
    for _ in range(30):
        p = MiniPet()
        p._begin_wander()
        if p._wander_target_x is None:
            continue
        target = p._wander_target_x
        p.drain_walk()
        assert p.x == target, f"应停在目标点：x={p.x} target={target}"
        assert p._wander_target_x is None, "走完后应清掉目标"
        return
    pytest.fail("没有产生可走的漫步目标")


def test_wander_never_leaves_screen():
    random.seed(7)
    for _ in range(300):
        p = MiniPet()
        p.x = random.choice([0.0, 1.0, 5.0, 900.0, 1739.0, 1740.0])
        p._begin_wander()
        p.drain_walk()
        assert 0 <= p.x <= p.screen_w - p.pet_size[0], f"走出屏幕: x={p.x}"


def test_wander_moves_pet():
    random.seed(3)
    p = MiniPet()
    start = p.x
    p._begin_wander()
    p.drain_walk()
    assert p.x != start
    assert p.moves > 0, "应调用 _move 刷新窗口位置"


def test_no_wander_during_game():
    p = MiniPet(game_active=True)
    p._start_wander_loop()
    p.root.drain()
    assert p.x == 500.0, "游戏进行中不应移动桌宠"
    assert p.moves == 0


def test_no_wander_while_dragging():
    p = MiniPet()
    p.is_dragging = True
    assert p._wander_allowed() is False


def test_no_wander_during_inertia():
    p = MiniPet()
    p.inertia_active = True
    assert p._wander_allowed() is False


def test_no_wander_while_talking():
    p = MiniPet()
    p.is_dialog_showing = True
    assert p._wander_allowed() is False
    p.is_dialog_showing = False
    p.is_auto_talking = True
    assert p._wander_allowed() is False


def test_no_wander_while_hovered():
    p = MiniPet()
    p.is_hovering = True
    assert p._wander_allowed() is False


def test_pause_wander_blocks_movement():
    p = MiniPet()
    p._pause_wander(seconds=999)
    assert p._wander_allowed() is False
    assert time.time() < p._wander_pause_until


def test_pause_wander_expires():
    p = MiniPet()
    p._pause_wander(seconds=0)
    assert p._wander_allowed() is True


def test_wander_suppressed_while_stopped():
    p = MiniPet()
    p.running = False
    assert p._wander_allowed() is False
    p._schedule_wander()
    assert p.root.q == [], "已停止时不应再排程"


def test_wander_reschedules_itself():
    random.seed(11)
    p = MiniPet()
    p._start_wander_loop()
    assert len(p.root.q) == 1, "启动后应排一次漫步"
    p.root.drain()
    assert len(p.root.q) == 1, "一次漫步结束后应重新排下一次"


def test_wander_interval_within_config():
    random.seed(21)
    p = MiniPet()
    for _ in range(200):
        p.root.q.clear()
        p._schedule_wander()
        ms = p.root.q[0][0]
        assert cfg.WANDER_MIN_INTERVAL * 1000 <= ms <= cfg.WANDER_MAX_INTERVAL * 1000


def test_too_close_target_skips_movement():
    """贴着右边缘时目标会被夹到当前位置，这时不该白跑一趟。"""
    p = MiniPet()
    for _ in range(60):
        p.x = float(p.screen_w - p.pet_size[0])
        p._wander_target_x = None
        p.moves = 0
        p._begin_wander()
        if abs(p.x - float(p.screen_w - p.pet_size[0])) < 0.001 and p.moves == 0:
            assert p._wander_target_x is None
            return
    pytest.fail("贴边时应出现「目标过近所以不走」的情形")
