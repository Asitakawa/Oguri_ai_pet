"""安排表系统"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timedelta

from core.paths import get_data_path
from utils.logger import get_logger

log = get_logger("reminder")

DATA_FILE = get_data_path("reminders.json")
CHECK_INTERVAL = 30
_WDAY = ["周一","周二","周三","周四","周五","周六","周日"]


def _disp_len(s):
    return sum(2 if ord(c) > 0x2e80 else 1 for c in s)

def _pad(s, w):
    return s + " " * max(0, w - _disp_len(s))


class ScheduleItem:
    __slots__ = ("id", "title", "type", "days", "hour", "minute",
                 "trigger_at", "enabled", "last_fired", "tag")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k, None if k in ("trigger_at","last_fired") else
                                    ([] if k == "days" else "" if k in ("title","id","tag") else 0 if k in ("hour","minute") else True)))

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    def desc(self):
        t = self.type
        if t in ("once", "delayed"):
            return f"{self.hour:02d}:{self.minute:02d}"
        if t == "daily":
            return f"每天{self.hour:02d}:{self.minute:02d}"
        if t == "weekly":
            ds = self.days or []
            if ds == [0, 1, 2, 3, 4]:
                label = "工作日"
            elif ds == [5, 6]:
                label = "周末"
            else:
                label = "、".join(_WDAY[d] for d in ds)
            return f"每{label}{self.hour:02d}:{self.minute:02d}"
        return f"{self.hour:02d}:{self.minute:02d}"

    def sort_key(self):
        return self.hour * 60 + self.minute

    def tag_label(self):
        return {"work":"工作","personal":"个人","health":"健康"}.get(self.tag, "")


class ScheduleManager:
    def __init__(self, pet):
        self.pet = pet
        self._lock = threading.Lock()
        self._items = []
        self._running = True
        self._load()
        self._thread = threading.Thread(target=self._scheduler, daemon=True)
        self._thread.start()

    def _load(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                with self._lock:
                    self._items = [ScheduleItem(**d) for d in raw if isinstance(d, dict)]
        except Exception:
            with self._lock:
                self._items = []

    def _save(self):
        with self._lock:
            snap = [it.to_dict() for it in self._items]
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
        except IOError as e:
            log.warning("安排表保存失败: %s", e)

    def add(self, schedule_type, hour, minute, title, days=None, tag=""):
        it = ScheduleItem(id=str(uuid.uuid4())[:8], title=title,
                          type=schedule_type, days=days or [],
                          hour=hour, minute=minute, tag=tag, enabled=True)
        with self._lock:
            self._items.append(it)
        self._save()
        return it

    def add_delayed(self, seconds, title, tag=""):
        dt = datetime.now() + timedelta(seconds=seconds)
        it = ScheduleItem(id=str(uuid.uuid4())[:8], title=title,
                          type="delayed", hour=dt.hour, minute=dt.minute,
                          trigger_at=dt.isoformat(), tag=tag, enabled=True)
        with self._lock:
            self._items.append(it)
        self._save()
        return it

    def list_all(self):
        with self._lock:
            return list(self._items)

    def list_active(self):
        with self._lock:
            return [it for it in self._items if it.enabled]

    def list_archive(self):
        with self._lock:
            return [it for it in self._items if not it.enabled]

    def remove(self, rid):
        with self._lock:
            self._items = [it for it in self._items if it.id != rid]
        self._save()

    def remove_by_index(self, index, source=None):
        src = source if source is not None else self.list_active()
        if 0 <= index < len(src):
            self.remove(src[index].id)
            return src[index]
        return None

    def update_by_index(self, index, source=None, **kw):
        src = source if source is not None else self.list_active()
        if not (0 <= index < len(src)):
            return None
        rid = src[index].id
        with self._lock:
            for it in self._items:
                if it.id == rid:
                    for k, v in kw.items():
                        if hasattr(it, k):
                            setattr(it, k, v)
                    it.trigger_at = None
                    it.last_fired = None
                    break
        self._save()
        return src[index]

    def search(self, keyword):
        kw = keyword.lower()
        return [it for it in self.list_active() if kw in it.title.lower()]

    def _sorted_active(self):
        return sorted(self.list_active(), key=lambda it: it.sort_key())

    def format_list(self):
        active = self._sorted_active()
        if not active:
            return "暂无安排"
        rows = [(i, it.desc(), it.title, it.tag_label())
                for i, it in enumerate(active, 1)]
        tw = max((_disp_len(r[1]) for r in rows), default=4)
        nw = max((_disp_len(r[2][:10]) for r in rows), default=4)
        lw = 5
        sep = f"├────┼{'─'*(tw+2)}┼{'─'*(nw+2)}┼{'─'*(lw+2)}┤"
        lines = [f"┌────┬{'─'*(tw+2)}┬{'─'*(nw+2)}┬{'─'*(lw+2)}┐",
                 f"│ {'#':>2} │ {'时间':<{tw}} │ {'事项':<{nw}} │ {'标签':<{lw}} │", sep]
        for i, when, title, tag in rows:
            lines.append(f"│ {i:>2} │ {_pad(when,tw)} │ {_pad(title[:10],nw)} │ {_pad(tag,lw)} │")
        lines.append(f"└────┴{'─'*(tw+2)}┴{'─'*(nw+2)}┴{'─'*(lw+2)}┘")
        return "\n".join(lines)

    def format_timeline(self):
        now = datetime.now()
        today = now.date()
        groups = {"今天": [], "明天": [], "本周": [], "更早": []}
        for it in self._sorted_active():
            if it.type == "daily":
                groups["今天"].append(it)
            elif it.type == "weekly":
                wd = now.weekday()
                if wd in (it.days or []):
                    groups["今天"].append(it)
                else:
                    groups["本周"].append(it)
            elif it.type in ("once", "delayed"):
                dt = datetime.fromisoformat(it.trigger_at).date() if it.trigger_at else today
                diff = (dt - today).days
                if diff == 0:
                    groups["今天"].append(it)
                elif diff == 1:
                    groups["明天"].append(it)
                elif 1 < diff < 7:
                    groups["本周"].append(it)
                else:
                    groups["更早"].append(it)
        lines = []
        for label in ("今天", "明天", "本周", "更早"):
            its = groups[label]
            if not its:
                continue
            lines.append(f"\n── {label} ──")
            for it in its:
                lines.append(f"  {it.desc()}  {it.title}{' ('+it.tag_label()+')' if it.tag_label() else ''}")
        return "\n".join(lines) if len(lines) > 1 else "暂无安排"

    def format_today(self):
        now = datetime.now()
        lines = ["── 今日安排 ──"]
        for it in self._sorted_active():
            if it.type == "daily":
                lines.append(f"  {it.desc()}  {it.title}")
            elif it.type == "weekly" and now.weekday() in (it.days or []):
                lines.append(f"  {it.desc()}  {it.title}")
            elif it.type in ("once", "delayed") and it.trigger_at:
                dt = datetime.fromisoformat(it.trigger_at).date()
                if dt == now.date():
                    lines.append(f"  {it.desc()}  {it.title}")
        return "\n".join(lines) if len(lines) > 1 else "今天暂无安排"

    # ── 调度 ────────────────────────────────
    def stop(self):
        self._running = False

    def _scheduler(self):
        while self._running:
            try:
                now = datetime.now()
                with self._lock:
                    snap = list(self._items)
                for it in snap:
                    if not it.enabled:
                        continue
                    with self._lock:
                        if it not in self._items:
                            continue
                    if self._should_fire(it, now):
                        self._fire(it)
            except Exception as e:
                log.warning("调度异常: %s", e)
            time.sleep(CHECK_INTERVAL)

    def _should_fire(self, it: "ScheduleItem", now) -> bool:
        if it.trigger_at:
            if now >= datetime.fromisoformat(it.trigger_at):
                return True
            return False
        if it.last_fired:
            last = datetime.fromisoformat(it.last_fired) if isinstance(it.last_fired, str) else it.last_fired
            if it.type == "once":
                return False
            if it.type in ("daily",) and last.date() == now.date():
                return False
            if it.type == "weekly" and last.date() == now.date():
                return False
        if now.hour != it.hour or now.minute != it.minute:
            return False
        if it.type == "once":
            return True
        if it.type == "daily":
            return True
        if it.type == "weekly":
            return now.weekday() in (it.days or [])
        return False

    def _fire(self, it):
        is_temp = it.type in ("once", "delayed")
        with self._lock:
            it.last_fired = datetime.now().isoformat()
            if is_temp:
                self._items = [x for x in self._items if x.id != it.id]
        self._save()
        if self.pet.root:
            self.pet.root.after(0, lambda: (
                self.pet.show_talk(f"时间到了：{it.title}"),
                self.pet.root.after(5000, self.pet.hide_talk),
            ))
