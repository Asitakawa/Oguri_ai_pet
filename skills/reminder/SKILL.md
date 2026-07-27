---
name: reminder
description: 设置提醒。当用户说"提醒我"、"记得"、"叫我"、"提醒"等情况时使用。支持相对时间（如"一分钟后"）和绝对时间（如"下午六点"）。
---

# Reminder Tool

设置一次性的、每天的、或工作日的定时提醒。

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 提醒内容，如"该下班了"、"起立活动" |
| delay_minutes | number | 否 | 相对时间，多少分钟后提醒。与 hour/minute 二选一 |
| hour | number | 否 | 绝对时间，小时（0-23）。与 delay_minutes 二选一 |
| minute | number | 否 | 绝对时间，分钟（0-59） |
| days | string | 否 | 重复模式：空=一次，daily=每天，weekdays=工作日(周一到周五) |

## Examples

一分钟后提醒起立：
```json
{"message": "起立活动一下", "delay_minutes": 1}
```

每天下午6点提醒下班：
```json
{"message": "下班了", "hour": 18, "minute": 0, "days": "daily"}
```

工作日中午12点提醒吃饭：
```json
{"message": "该吃饭了", "hour": 12, "minute": 0, "days": "weekdays"}
```
