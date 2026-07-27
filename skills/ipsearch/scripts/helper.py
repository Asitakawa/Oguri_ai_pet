"""查看当前网络 IP 地址"""
import requests

NAME = "查看本机IP"
DESCRIPTION = "获取当前电脑的公网 IP 地址、所在地和网络运营商信息"


def execute(_pet=None) -> str:
    try:
        r = requests.get("https://ip-api.com/json/?lang=zh-CN", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return f"IP: {d.get('query','')} | 位置: {d.get('country','')}{d.get('regionName','')}{d.get('city','')} | 运营商: {d.get('isp','')}"
        return "暂时查不到 IP"
    except Exception as e:
        return f"查询失败: {e}"
