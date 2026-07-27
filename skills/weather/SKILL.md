---
name: get_weather
description: 查询指定城市的当前天气。当用户问天气、温度、多少度、冷不冷、下雨等情况时使用。参数 city 传入城市名。
---

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| city | string | 是 | 城市名，支持中文（深圳）或英文（shenzhen） |

## 返回值

返回天气数据：天气状况、温度、湿度、风速。

## 示例

用户说"深圳今天冷吗" → 调用 get_weather(city="深圳")
用户说"北京天气" → 调用 get_weather(city="北京")
