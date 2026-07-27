"""Backend: 天气查询"""
import requests


def execute(city: str, _pet=None) -> str:
    url = f"https://wttr.in/{city}?format=%C|%t|%h|%w|%p&lang=zh"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "curl/7.68.0"})
        if resp.status_code == 200:
            parts = resp.text.strip().split("|")
            desc = parts[0] if len(parts) > 0 else "未知"
            temp = parts[1] if len(parts) > 1 else ""
            humid = parts[2] if len(parts) > 2 else ""
            wind = parts[3] if len(parts) > 3 else ""
            rain = parts[4] if len(parts) > 4 else ""
            return f"城市: {city} | 天气: {desc} | 温度: {temp} | 湿度: {humid} | 风速: {wind} | 降水量: {rain}"
        return f"无法获取{city}的天气信息"
    except Exception as e:
        return f"天气查询失败: {e}"
