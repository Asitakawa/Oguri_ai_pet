"""Backend: 安排表 — 支持 list/timeline/today/search/add/delete/done"""
from datetime import datetime


def _int(v):
    """宽松整数解析：None 或无法解析时返回 None（不抛异常）"""
    if v is None:
        return None
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return None


def _is_all(v):
    """判断是否为 'all'（忽略大小写与空白）"""
    return str(v).strip().lower() == "all"


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
        idx = _int(number)
        if idx is None:
            if _is_all(number):
                active = sm.list_active()
                for it in active:
                    sm.remove(it.id)
                return f"已删除全部 {len(active)} 条安排" if active else "当前没有待删除的安排"
            return f"无效编号: {number}"
        if idx < 1:
            return "编号从 1 开始"
        removed = sm.remove_by_index(idx - 1)
        return f"已删除: {removed.title}" if removed else f"第{number}个不存在"

    # 标记完成
    if action == "done":
        if number is None:
            return "要标记第几个？"
        idx = _int(number)
        if idx is None:
            if _is_all(number):
                active = sm.list_active()
                for it in active:
                    sm.remove(it.id)
                return f"已标记完成全部 {len(active)} 条安排" if active else "当前没有待完成的安排"
            return f"无效编号: {number}"
        if idx < 1:
            return "编号从 1 开始"
        active = sm.list_active()
        j = idx - 1
        if 0 <= j < len(active):
            it = active[j]
            sm.remove(it.id)
            return f"已标记完成: {it.title}"
        return f"第{number}个不存在"

    # 添加
    if delay_minutes is not None:
        dm = _int(delay_minutes)
        if dm is None or dm < 0:
            return f"无效的延迟分钟数: {delay_minutes}"
        sm.add_delayed(dm * 60, title or "提醒", tag=tag)
        return f"{dm}分钟后: {title or '提醒'}"

    h = _int(hour)
    if h is None:
        h = datetime.now().hour
    m = _int(minute)
    if m is None:
        m = 0

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
