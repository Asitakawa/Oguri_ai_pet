---
name: weather
description: 查询指定城市的当前天气。当用户询问天气、温度、下雨、多少度、冷不冷等情况时使用。
---

# Weather Tool

Single tool for querying weather.

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| city | string | 是 | 城市名，如"深圳"、"北京"、"上海" |

## Returns

返回天气数据字符串，包含城市、天气状况、温度、湿度、风速。

## Examples

用户说"深圳今天冷吗" → 调用 `get_weather` 获取数据后回复
用户说"北京天气怎么样" → 同上
