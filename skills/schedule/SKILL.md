---
name: schedule
description: 管理安排表。支持查看（表格/时间线/今日/搜索）、添加、删除、标记完成。用户说"安排表"、"有什么安排"、"提醒我"、"添加提醒"、"删除安排"、"今日安排"等情况时使用。单次提醒触发后自动删除。
---

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | 是 | list（表格）/timeline（时间线）/today（今日）/search（搜索）/add（添加）/delete（删除）/done（完成）/archive（已完成） |
| title | string | 否 | 事项内容，add 时必填 |
| delay_minutes | number | 否 | 多少分钟后触发 |
| hour | number | 否 | 小时 0-23 |
| minute | number | 否 | 分钟 0-59 |
| days | string | 否 | daily/weekdays/weekend/空（一次） |
| number | number | 否 | 编号，delete/done 时使用；传 all 可删除/完成全部安排 |
| keyword | string | 否 | 搜索关键词，search 时使用 |
| tag | string | 否 | 标签：work/personal/health |

## 关键行为

- 单次提醒（没有说每天/每周）触发后自动删除
- 每天/每周/工作日/周末等重复提醒持续有效
- action=list 按时间排序，带标签列
- action=timeline 按今天/明天/本周分组显示
