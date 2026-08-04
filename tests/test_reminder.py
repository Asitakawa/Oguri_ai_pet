"""安排表：触发判定 / 单次自动删除 / 格式化"""
from datetime import datetime

from core.reminder import ScheduleItem, ScheduleManager


class DummyPet:
    root = None


def _manager(tmp_path, monkeypatch):
    monkeypatch.setattr("core.reminder.DATA_FILE", str(tmp_path / "reminders.json"))
    m = ScheduleManager(DummyPet())
    m.stop()  # 停止后台调度线程，仅测逻辑
    return m


def test_should_fire_once_at_time(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    now = datetime.now()
    it = ScheduleItem(id="1", title="t", type="once", hour=now.hour,
                      minute=now.minute, enabled=True)
    assert m._should_fire(it, now) is True
    it.last_fired = now.isoformat()
    assert m._should_fire(it, now) is False


def test_should_fire_daily_dedup(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    now = datetime.now()
    it = ScheduleItem(id="1", title="t", type="daily", hour=now.hour,
                      minute=now.minute, enabled=True)
    assert m._should_fire(it, now) is True
    it.last_fired = now.isoformat()
    assert m._should_fire(it, now) is False


def test_should_fire_weekly_only_matching_weekday(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    now = datetime.now()
    it = ScheduleItem(id="1", title="t", type="weekly", days=[now.weekday()],
                      hour=now.hour, minute=now.minute, enabled=True)
    assert m._should_fire(it, now) is True
    it2 = ScheduleItem(id="2", title="t", type="weekly", days=[(now.weekday() + 1) % 7],
                       hour=now.hour, minute=now.minute, enabled=True)
    assert m._should_fire(it2, now) is False


def test_should_fire_delayed_trigger_at(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    it = ScheduleItem(id="1", title="t", type="delayed",
                      trigger_at=datetime.now().isoformat(), enabled=True)
    assert m._should_fire(it, datetime.now()) is True
    from datetime import timedelta
    it2 = ScheduleItem(id="2", title="t", type="delayed",
                       trigger_at=(datetime.now() + timedelta(hours=1)).isoformat(),
                       enabled=True)
    assert m._should_fire(it2, datetime.now()) is False


def test_fire_removes_once_item(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    it = m.add("once", datetime.now().hour, datetime.now().minute, "临时提醒")
    assert it in m.list_active()
    m._fire(it)
    assert it not in m.list_active()


def test_add_search_remove(tmp_path, monkeypatch):
    m = _manager(tmp_path, monkeypatch)
    m.add("daily", 8, 0, "晨跑", tag="health")
    m.add("weekly", 20, 0, "开会", days=[0, 1, 2, 3, 4], tag="work")
    assert len(m.list_active()) == 2
    hits = m.search("晨跑")
    assert len(hits) == 1
    assert "每天08:00" in m.format_today()
    m.remove(hits[0].id)
    assert len(m.list_active()) == 1


def test_schedule_item_desc(tmp_path, monkeypatch):
    assert ScheduleItem(id="1", type="daily", hour=8, minute=5).desc() == "每天08:05"
    assert ScheduleItem(id="2", type="weekly", days=[5, 6], hour=9, minute=0).desc() == "每周末09:00"
    assert ScheduleItem(id="3", type="once", hour=1, minute=2).desc() == "01:02"
