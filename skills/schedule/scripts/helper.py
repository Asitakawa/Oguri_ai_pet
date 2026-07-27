"""Backend: 安排表 — 支持 list/timeline/today/search/add/delete/done"""
from datetime import datetime


def _int(v):
    return int(float(str(v))) if v is not None else None


def execute(action="add", title=None, delay_minutes=None,
            hour=None, minute=None, days=None, number=None,
            keyword=None, tag="", _pet=None):
    sm = _pet.schedule_manager if _pet else None
    if not sm:
        return "安排服务不可用"

    # 查看 - 表格
    if action == "list":
        return sm.format_list()

    # 查看 - 时间线
    if action == "timeline":
        return sm.format_timeline()

    # 查看 - 今日
    if action == "today":
        return sm.format_today()

    # 搜索
    if action == "search":
        if not keyword:
            return "请输入关键词"
        hits = sm.search(keyword)
        if not hits:
            return f"没有找到包含「{keyword}」的安排"
        return "\n".join(f"{i}. {it.desc()} {it.title}" for i, it in enumerate(hits, 1))

    # 查看已完成
    if action == "archive":
        arch = sm.list_archive()
        if not arch:
            return "没有已完成的安排"
        return "\n".join(f"{i}. {it.desc()} {it.title}" for i, it in enumerate(arch, 1))

    # 删除
    if action == "delete":
        if number is None:
            return "要删除第几个？"
        removed = sm.remove_by_index(_int(number) - 1)
        return f"已删除: {removed.title}" if removed else f"第{number}个不存在"

    # 标记完成
    if action == "done":
        if number is None:
            return "要标记第几个？"
        active = sm.list_active()
        idx = _int(number) - 1
        if 0 <= idx < len(active):
            it = active[idx]
            sm.remove(it.id)
            return f"已标记完成: {it.title}"
        return f"第{number}个不存在"

    # 添加
    if delay_minutes is not None:
        dm = _int(delay_minutes)
        sm.add_delayed(dm * 60, title or "提醒", tag=tag)
        return f"{dm}分钟后: {title or '提醒'}"

    h = _int(hour) if hour is not None else datetime.now().hour
    m = _int(minute) if minute is not None else 0

    if days == "daily":
        sm.add("daily", h, m, title or "提醒", tag=tag)
        return f"每天 {h:02d}:{m:02d} → {title or '提醒'}"
    if days == "weekdays":
        sm.add("weekly", h, m, title or "提醒", [0, 1, 2, 3, 4], tag=tag)
        return f"工作日 {h:02d}:{m:02d} → {title or '提醒'}"
    if days == "weekend":
        sm.add("weekly", h, m, title or "提醒", [5, 6], tag=tag)
        return f"周末 {h:02d}:{m:02d} → {title or '提醒'}"
    sm.add("once", h, m, title or "提醒", tag=tag)
    return f"{h:02d}:{m:02d} → {title or '提醒'}"
