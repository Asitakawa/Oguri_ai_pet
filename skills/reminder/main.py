"""Backend: 时间提醒 — 支持 list/add/delete/modify"""
from datetime import datetime, timedelta


def execute(action: str = "add", message: str = None,
            delay_minutes: int = None, hour: int = None, minute: int = None,
            days: str = None, number: int = None, _pet=None) -> str:
    rm = _pet.reminder_manager if _pet else None
    if not rm:
        return "提醒服务不可用"

    # ── 查看列表 ──────────────────────────────
    if action == "list":
        return rm.format_list()

    idx = int(float(str(number))) if number is not None else None

    # ── 删除 ──────────────────────────────────
    if action == "delete":
        if idx is None:
            return "请指定要删除的提醒编号"
        removed = rm.remove_by_index(idx - 1)
        if removed:
            return f"已删除第{idx}个提醒: {removed['message']}"
        return f"第{idx}个提醒不存在"

    # ── 修改 ──────────────────────────────────
    if action == "modify":
        if idx is None:
            return "请指定要修改的提醒编号"
        updates = {}
        if message is not None:
            updates["message"] = message
        if hour is not None:
            updates["hour"] = int(float(str(hour)))
        if minute is not None:
            updates["minute"] = int(float(str(minute)))
        if days is not None:
            updates["days"] = [] if days == "once" else [0, 1, 2, 3, 4] if days == "weekdays" else []
            updates["schedule_type"] = "once" if days in ("", None) else "daily" if days == "daily" else "weekly"
        if delay_minutes is not None:
            dm = int(float(str(delay_minutes)))
            updates["trigger_at"] = (datetime.now() + timedelta(minutes=dm)).isoformat()
            updates["schedule_type"] = "once"
        updated = rm.update_by_index(idx - 1, **updates)
        if updated:
            return f"已修改第{idx}个提醒"
        return f"第{idx}个提醒不存在"

    # ── 添加（默认） ──────────────────────────
    now = datetime.now()

    if delay_minutes is not None:
        dm = int(float(str(delay_minutes)))
        rm.add_delayed(dm * 60, message)
        return f"已设置 {dm} 分钟后提醒: {message}"

    h = int(float(str(hour))) if hour is not None else now.hour
    m = int(float(str(minute))) if minute is not None else 0

    if days == "daily":
        rm.add("daily", h, m, message, [])
        return f"已设置每天 {h:02d}:{m:02d} 提醒: {message}"
    elif days == "weekdays":
        rm.add("weekly", h, m, message, [0, 1, 2, 3, 4])
        return f"已设置工作日 {h:02d}:{m:02d} 提醒: {message}"
    else:
        rm.add("once", h, m, message, [])
        return f"已设置 {h:02d}:{m:02d} 提醒: {message}"
