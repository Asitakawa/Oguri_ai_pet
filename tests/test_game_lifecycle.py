"""小游戏生命周期：BaseGame 契约 + 一飞冲天抛高物理

这些用例不创建真实 Tk 窗口，用最小假对象替代 pet.root / pet.label。
回归目标（重构前均不成立）：
- 回调触发后会从 _after_ids 摘除，长时间游戏不会让集合无限膨胀
- 计分板 <B1-Motion> 绑到 _counter_motion（此前误绑 _counter_press，导致拖不动）
- fly_high 继承 BaseGame，退出时能清理 after、还原桌宠位置
- fly_high 退出后不会把落地台词漏到下一局
"""
from __future__ import annotations

import pytest

from core import config as cfg
from game.base import BaseGame
from game.fly_high.game import FlyHighGame


# ── 假对象 ──────────────────────────────
class FakeLabel:
    def __init__(self) -> None:
        self.bound: dict = {}

    def bind(self, seq, func):
        self.bound[seq] = func

    def unbind(self, seq, func=None):
        self.bound.pop(seq, None)


class FakeRoot:
    """可控的 after 调度器：callbacks 只在 flush_* 时执行，便于断言清理行为。"""

    def __init__(self) -> None:
        self.queue: dict = {}
        self.cancelled: list = []
        self.all_bindings: dict = {}
        self._n = 0

    def after(self, delay_ms, func=None, *args):
        self._n += 1
        aid = f"after#{self._n}"
        self.queue[aid] = (func, args)
        return aid

    def after_cancel(self, aid):
        self.cancelled.append(aid)
        self.queue.pop(aid, None)

    def bind_all(self, sequence, func):
        self.all_bindings[sequence] = func

    def unbind_all(self, sequence):
        self.all_bindings.pop(sequence, None)

    def flush(self):
        """执行并清空当前所有排队回调（回调内新注册的不会被执行）。"""
        items = list(self.queue.items())
        self.queue.clear()
        for _aid, (func, args) in items:
            if func is not None:
                func(*args)


class FakePet:
    def __init__(self, screen_w=1920, screen_h=1080, size=(180, 180)) -> None:
        self.root = FakeRoot()
        self.label = FakeLabel()
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.pet_size = size
        self.x = 100.0
        self.y = 200.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.is_dragging = False
        self._cur_img_key = "stay"
        self._hide_timer = None
        self.talks: list = []
        self.moves = 0
        # 模拟真实桌宠：交互方法在初始化时就绑到 label 上，
        # 否则验证不了「游戏期间被替换为 noop / 结束后恢复」
        for seq, attr in (
            ("<ButtonPress-1>", "_on_drag_start"),
            ("<B1-Motion>", "_on_drag_move"),
            ("<ButtonRelease-1>", "_on_drag_end"),
            ("<Double-Button-1>", "_on_double_click"),
            ("<Button-2>", "_on_middle_click"),
            ("<Enter>", "_on_enter"),
            ("<Leave>", "_on_leave"),
        ):
            if hasattr(self, attr):
                self.label.bind(seq, getattr(self, attr))

    # 桌宠被游戏调用的方法
    def _move(self):
        self.moves += 1

    def show_talk(self, text):
        self.talks.append(text)

    def hide_talk(self):
        self.talks.append("<hide>")

    def _set_pet_image(self, key):
        self._cur_img_key = key

    def _cancel_click_timer(self):
        pass

    def stop_all_animations(self):
        pass

    def _on_drag_end(self, event=None):
        self.drag_end_called = True

    # 以下四个是 BaseGame._PET_BINDINGS 会引用到的桌宠交互，
    # 必须存在才能验证「游戏期间被替换为 noop」
    def _on_drag_start(self, event=None):
        pass

    def _on_drag_move(self, event=None):
        pass

    def _on_double_click(self, event=None):
        pass

    def _on_middle_click(self, event=None):
        pass

    def _on_enter(self, event=None):
        pass

    def _on_leave(self, event=None):
        pass


class NoCounterGame(BaseGame):
    """不建计数器窗口（tk.Toplevel/tk.Frame 需要真实 Tk root）。

    计数器本身由 test_base_counter_drag_uses_motion_handler 与
    test_fly_high_counter_uses_meters 用假控件单独覆盖。
    """

    NAME = "测试游戏"

    def _create_counter(self):
        pass

    def _destroy_counter(self):
        pass


class FakeToplevel:
    def __init__(self) -> None:
        self.geometry_calls: list = []
        self.destroyed = False

    def overrideredirect(self, *_a):
        pass

    def attributes(self, *_a):
        pass

    def configure(self, **_k):
        pass

    def geometry(self, spec=None):
        if spec is not None:
            self.geometry_calls.append(spec)

    def destroy(self):
        self.destroyed = True


# ── BaseGame 契约 ────────────────────────
def test_base_schedule_prunes_fired_callbacks():
    pet = FakePet()
    g = NoCounterGame(pet)
    g.start()
    try:
        before = len(g._after_ids)  # start() 自己会排「规则台词」的隐藏回调
        for _ in range(5):
            g._schedule(10, lambda: None)
        assert len(g._after_ids) == before + 5
        pet.root.flush()  # 全部触发 → 应自行摘除
        assert len(g._after_ids) == 0, "回调触发后必须从 _after_ids 移除"
    finally:
        g.stop()


def test_base_stop_cancels_pending_callbacks():
    pet = FakePet()
    g = NoCounterGame(pet)
    g.start()
    aid = g._schedule(10_000, lambda: None)
    assert aid in g._after_ids
    assert aid in pet.root.queue, "延迟回调此时应仍在排队"
    g.stop()
    assert len(g._after_ids) == 0
    assert aid in pet.root.cancelled, "stop() 必须取消它"
    assert pet.root.queue == {}, "stop() 后不应残留待执行回调"


def test_base_stop_is_idempotent():
    pet = FakePet()
    g = NoCounterGame(pet)
    g.start()
    g.stop()
    g.stop()  # 不应抛异常
    assert g.is_active() is False


def test_base_restores_pet_position_and_bindings():
    pet = FakePet()
    g = NoCounterGame(pet)
    g.start()
    # 游戏期间桌宠交互被换成 noop
    assert pet.label.bound["<Double-Button-1>"] == g._noop
    pet.x, pet.y = 500.0, 600.0
    g.stop()
    assert (pet.x, pet.y) == (100.0, 200.0), "stop() 应还原桌宠位置"
    assert pet._cur_img_key == "stay"


def test_base_passthrough_keeps_binding_live():
    """_PASSTHROUGH_BINDINGS 里的交互不被覆盖，由游戏自己另绑。"""

    class DragGame(NoCounterGame):
        _PASSTHROUGH_BINDINGS = frozenset({"<ButtonRelease-1>"})

    pet = FakePet()
    original = pet._on_drag_end
    g = DragGame(pet)
    g.start()
    try:
        # 未被覆盖为 noop，仍是桌宠原本的处理函数
        assert pet.label.bound["<ButtonRelease-1>"] == original
        # 不在 _pet_originals 里 → stop() 不会拿它去覆盖游戏自己绑的处理函数
        assert "<ButtonRelease-1>" not in g._pet_originals
        # 其余交互照常禁用
        assert pet.label.bound["<Double-Button-1>"] == g._noop
    finally:
        g.stop()


class _FakePanel:
    def __init__(self) -> None:
        self.bound: dict = {}

    def bind(self, seq, func):
        self.bound[seq] = func

    def winfo_children(self):
        return []


def test_base_counter_drag_uses_motion_handler():
    """计分板必须绑 _counter_motion，否则拖不动（回归点）。"""
    pet = FakePet()
    g = NoCounterGame(pet)
    g._counter_panel = _FakePanel()
    g._set_counter_draggable(True)
    bound = g._counter_panel.bound
    assert bound["<ButtonPress-1>"] == g._counter_press
    assert bound["<B1-Motion>"] == g._counter_motion


def test_base_counter_drag_disabled_binds_noop():
    pet = FakePet()
    g = NoCounterGame(pet)
    g._counter_panel = _FakePanel()
    g._set_counter_draggable(False)
    bound = g._counter_panel.bound
    assert bound["<ButtonPress-1>"] == g._noop
    assert bound["<B1-Motion>"] == g._noop


# ── 一飞冲天 ─────────────────────────────
class FlyHighNoCounter(FlyHighGame):
    """跳过真实计数器窗口，其余生命周期走真实实现。"""

    def _create_counter(self):
        pass

    def _destroy_counter(self):
        pass


def test_fly_high_is_base_game():
    assert issubclass(FlyHighGame, BaseGame)
    pet = FakePet()
    assert isinstance(FlyHighGame(pet), BaseGame)


def test_fly_high_start_moves_pet_to_screen_bottom():
    pet = FakePet()
    g = FlyHighNoCounter(pet)
    g.start()
    try:
        assert pet.y == pet.screen_h - pet.pet_size[1]
        assert pet.label.bound["<ButtonRelease-1>"] is not None
        # 抛高依赖拖拽，这三个交互必须保留
        for seq in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>"):
            assert pet.label.bound.get(seq) != g._noop
        # 双击/悬停/中键应被禁用
        assert pet.label.bound["<Double-Button-1>"] == g._noop
        assert pet.label.bound["<Enter>"] == g._noop
    finally:
        g.stop()


def test_fly_high_stop_restores_original_position():
    pet = FakePet()
    g = FlyHighNoCounter(pet)
    g.start()
    g.stop()
    assert (pet.x, pet.y) == (100.0, 200.0), "退出游戏后应回到进入前的位置"


def test_fly_high_throw_below_threshold_returns_to_normal_interaction():
    pet = FakePet()
    pet.velocity_y = 5.0  # 向下甩：不触发飞行
    g = FlyHighNoCounter(pet)
    g.start()
    try:
        g._on_throw()
        assert getattr(pet, "drag_end_called", False) is True
        assert g._physics_id is None
    finally:
        g.stop()


def test_fly_high_throw_launches_and_lands():
    pet = FakePet()
    pet.velocity_y = -30.0
    pet.velocity_x = 4.0
    g = FlyHighNoCounter(pet)
    g.start()
    try:
        ground = g._ground_y
        g._on_throw()
        assert g._physics_id is not None, "向上甩应进入物理循环"
        # 推进物理直到落地
        for _ in range(2000):
            if g._physics_id is None:
                break
            pet.root.flush()
        assert g._physics_id is None, "应已落地并停止物理循环"
        assert pet.y == ground
        assert g._max_height > 0
    finally:
        g.stop()


# ── 脱手速度归一化（帧率无关） ────────────
def test_release_velocity_falls_back_to_frame_step_without_timestamps():
    """拿不到事件时间戳时，退化为「每事件位移 = 每帧位移」（旧行为）。"""
    pet = FakePet()
    pet.velocity_x = 5.0
    pet.velocity_y = -20.0
    pet._drag_event_times = []
    g = FlyHighNoCounter(pet)
    assert g._release_velocity() == (5.0, -20.0)


def test_release_velocity_is_normalized_by_event_interval():
    """同样的甩动速度，事件间隔不同应该得到同样的 px/帧。"""
    step_s = FlyHighGame.FRAME_MS / 1000.0

    # 慢速鼠标：每事件间隔 20ms，每事件位移 20px → 1000 px/s → 20 px/帧
    pet_slow = FakePet()
    pet_slow.velocity_y = -20.0
    pet_slow._drag_event_times = [0.00, 0.02, 0.04]
    g_slow = FlyHighNoCounter(pet_slow)
    vy_slow = g_slow._release_velocity()[1]
    assert vy_slow == pytest.approx(-20.0 / 0.02 * step_s)

    # 高回报率鼠标：同样 1000 px/s，但每事件间隔 4ms、每事件位移 4px
    pet_fast = FakePet()
    pet_fast.velocity_y = -4.0
    pet_fast._drag_event_times = [0.000, 0.004, 0.008]
    g_fast = FlyHighNoCounter(pet_fast)
    vy_fast = g_fast._release_velocity()[1]

    # 归一化后两者必须一致——这正是修复前做不到的
    assert vy_fast == pytest.approx(vy_slow), (
        f"不同轮询率下脱手速度不一致：慢 {vy_slow:.2f} vs 快 {vy_fast:.2f}"
    )


def test_release_velocity_ignores_zero_span():
    pet = FakePet()
    pet.velocity_y = -20.0
    pet._drag_event_times = [1.0, 1.0, 1.0]  # 时间戳相同，跨度为 0
    g = FlyHighNoCounter(pet)
    assert g._release_velocity()[1] == -20.0


def test_frame_rate_independence_of_achieved_height():
    """同样的物理甩动速度，应飞同样的高度，与鼠标事件率无关。"""
    heights = []
    for ev_dt, ev_px in ((0.020, -20.0), (0.004, -4.0)):
        pet = FakePet()
        pet.velocity_y = ev_px
        pet._drag_event_times = [0.0, ev_dt, 2 * ev_dt]
        g = FlyHighNoCounter(pet)
        g.start()
        try:
            g._on_throw()
            for _ in range(3000):
                if g._physics_id is None:
                    break
                pet.root.flush()
            heights.append(g._max_height)
        finally:
            g.stop()
    assert heights[0] == pytest.approx(heights[1], rel=1e-6), (
        f"不同事件率下飞行高度不同：{heights}"
    )


def test_fly_high_counter_uses_meters():
    pet = FakePet()
    g = FlyHighNoCounter(pet)
    g._counter_label = _FakeLabel()
    g._update_counter(25.0)  # PX_PER_METER = 10
    assert g._counter_label.text == "2.5 米"


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def config(self, **kw):
        if "text" in kw:
            self.text = kw["text"]


def test_fly_high_stop_discards_pending_landing_reply():
    """退出游戏时，尚未播报的落地台词必须被取消，不能漏进下一局。"""
    pet = FakePet()
    pet.velocity_y = -30.0
    g = FlyHighNoCounter(pet)
    g.start()
    g._on_throw()
    for _ in range(2000):
        if g._physics_id is None:
            break
        pet.root.flush()
    # 落地后应排了一个延迟回复
    pending = [aid for aid, (fn, _a) in pet.root.queue.items() if fn is not None]
    assert pending, "落地后应排入延迟回复"
    talks_before = len(pet.talks)
    g.stop()
    assert pet.root.queue == {}, "stop() 应取消延迟回复"
    pet.root.flush()
    assert len(pet.talks) == talks_before, "退出后不应再冒出落地台词"


# 台词分档的断言集中在 tests/test_game.py，这里只覆盖生命周期

def test_config_low_state_constants_exist():
    assert cfg.LOW_STATE_REPEAT_INTERVAL > 0
    assert cfg.LOW_STATE_RECOVER_MARGIN > 0
