"""Backend: 天气查询"""
import requests
import time

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_CITY_ALIAS = {
    "shanghai": "上海", "beijing": "北京", "shenzhen": "深圳",
    "guangzhou": "广州", "hangzhou": "杭州", "chengdu": "成都",
    "wuhan": "武汉", "nanjing": "南京", "chongqing": "重庆",
    "suzhou": "苏州", "tianjin": "天津", "shenyang": "沈阳",
    "dongguan": "东莞", "qingdao": "青岛", "xian": "西安",
    "kunming": "昆明", "dalian": "大连", "xiamen": "厦门",
}


def _normalize(city):
    c = city.strip().lower()
    if c in _CITY_ALIAS:
        return _CITY_ALIAS[c]
    return city


def execute(city: str, _pet=None) -> str:
    city = _normalize(city)
    url = f"https://wttr.in/{city}?format=%C|%t|%h|%w|%p&lang=zh"
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=8,
                                headers={"User-Agent": _UA})
            if resp.status_code == 200:
                parts = resp.text.strip().split("|")
                desc = parts[0] if len(parts) > 0 else "未知"
                temp = parts[1] if len(parts) > 1 else ""
                humid = parts[2] if len(parts) > 2 else ""
                wind = parts[3] if len(parts) > 3 else ""
                return f"{city}: {desc} {temp} 湿度{humid} 风速{wind}"
            return f"暂时查不到{city}的天气"
        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(1)
                continue
            return f"查询{city}天气超时了"
        except Exception as e:
            return f"查询失败: {e}"
