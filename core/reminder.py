"""提醒系统"""
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from utils.paths import get_data_path

DATA_FILE = get_data_path("reminders.json")
CHECK_INTERVAL = 30


class ReminderManager:
    def __init__(self, pet):
        self.pet = pet
        self._lock = threading.Lock()
        self._reminders = []
        self._running = True
        self._load()
        self._thread = threading.Thread(target=self._scheduler, daemon=True)
        self._thread.start()

    def _load(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                with self._lock:
                    self._reminders = data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError, FileNotFoundError):
            with self._lock:
                self._reminders = []

    def _save(self):
        with self._lock:
            snap = list(self._reminders)
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"提醒保存失败: {e}")

    def add(self, schedule_type, hour, minute, message, days=None):
        r = {
            "id": str(uuid.uuid4())[:8],
            "message": message,
            "schedule_type": schedule_type,
            "days": days or [],
            "hour": hour,
            "minute": minute,
            "trigger_at": None,
            "last_fired": None,
            "enabled": True,
        }
        with self._lock:
            self._reminders.append(r)
        self._save()
        return r

    def add_delayed(self, seconds, message):
        trigger_dt = datetime.now() + timedelta(seconds=seconds)
        r = {
            "id": str(uuid.uuid4())[:8],
            "message": message,
            "schedule_type": "once",
            "days": [],
            "hour": trigger_dt.hour,
            "minute": trigger_dt.minute,
            "trigger_at": trigger_dt.isoformat(),
            "last_fired": None,
            "enabled": True,
        }
        with self._lock:
            self._reminders.append(r)
        self._save()
        return r

    def list_active(self):
        with self._lock:
            return [r for r in self._reminders if r["enabled"]]

    def remove(self, rid):
        with self._lock:
            self._reminders = [r for r in self._reminders if r["id"] != rid]
        self._save()

    @staticmethod
    def _disp_len(s):
        return sum(2 if ord(c) > 0x2e80 else 1 for c in s)

    @staticmethod
    def _pad(s, width):
        visible = sum(2 if ord(c) > 0x2e80 else 1 for c in s)
        return s + ' ' * max(0, width - visible)

    def format_list(self):
        active = self.list_active()
        if not active:
            return "暂无提醒"
        rows = []
        for i, r in enumerate(active, 1):
            if r["schedule_type"] == "once":
                when = f"{r['hour']:02d}:{r['minute']:02d}"
            elif r["schedule_type"] == "daily":
                when = f"每天{r['hour']:02d}:{r['minute']:02d}"
            elif r["schedule_type"] == "weekly":
                ds = r.get("days", [])
                if ds == [0,1,2,3,4]:
                    label = "工作日"
                elif ds == [5,6]:
                    label = "周末"
                else:
                    label = "、".join(["周一","周二","周三","周四","周五","周六","周日"][d] for d in ds)
                when = f"{label}{r['hour']:02d}:{r['minute']:02d}"
            else:
                when = f"{r['hour']:02d}:{r['minute']:02d}"
            rows.append((i, when, r['message']))
        w = max(self._disp_len(r[1]) for r in rows) if rows else 0
        msg_w = max(self._disp_len(r[2][:10]) for r in rows) if rows else 10
        msg_w = max(msg_w, 4)
        lines = [f"┌────┬{'─' * (w+2)}┬{'─' * (msg_w+2)}┐",
                 f"│ {'#':>2} │ {'时间':<{w}} │ {'备注':<{msg_w}} │",
                 f"├────┼{'─' * (w+2)}┼{'─' * (msg_w+2)}┤"]
        for i, when, msg in rows:
            msg_s = msg[:10]
            lines.append(f"│ {i:>2} │ {self._pad(when, w)} │ {self._pad(msg_s, msg_w)} │")
        lines.append(f"└────┴{'─' * (w+2)}┴{'─' * (msg_w+2)}┘")
        return "\n".join(lines)

    def remove_by_index(self, index):
        active = self.list_active()
        if 0 <= index < len(active):
            self.remove(active[index]["id"])
            return active[index]
        return None

    def update_by_index(self, index, **updates):
        active = self.list_active()
        if not (0 <= index < len(active)):
            return None
        rid = active[index]["id"]
        with self._lock:
            for r in self._reminders:
                if r["id"] == rid:
                    r.update(updates)
                    r["trigger_at"] = None
                    r["last_fired"] = None
                    break
        self._save()
        return active[index]

    def stop(self):
        self._running = False

    def _scheduler(self):
        while self._running:
            try:
                now = datetime.now()
                with self._lock:
                    snap = list(self._reminders)
                for r in snap:
                    if not r["enabled"]:
                        continue
                    with self._lock:
                        if r not in self._reminders:
                            continue
                    if self._should_fire(r, now):
                        self._fire(r)
            except Exception as e:
                print(f"提醒调度异常: {e}")
            time.sleep(CHECK_INTERVAL)

    def _should_fire(self, r, now):
        if r.get("trigger_at"):
            if now >= datetime.fromisoformat(r["trigger_at"]):
                return True
            return False

        if r.get("last_fired"):
            last = r["last_fired"]
            if isinstance(last, str):
                last_dt = datetime.fromisoformat(last)
                if r["schedule_type"] == "once":
                    return False
                if r["schedule_type"] == "daily" and last_dt.date() == now.date():
                    return False
                if r["schedule_type"] == "weekly" and last_dt.date() == now.date():
                    return False

        if now.hour != r["hour"] or now.minute != r["minute"]:
            return False
        if r["schedule_type"] == "once":
            return True
        if r["schedule_type"] == "daily":
            return True
        if r["schedule_type"] == "weekly":
            return now.weekday() in r.get("days", [])
        return False

    def _fire(self, r):
        with self._lock:
            r["last_fired"] = datetime.now().isoformat()
            if r["schedule_type"] == "once":
                r["enabled"] = False
        self._save()
        if self.pet.root:
            self.pet.root.after(0, lambda: self.pet.show_talk(f"⏰ {r['message']}"))
