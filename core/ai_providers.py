"""API 厂商预设"""
import base64
import os
import requests
from dotenv import load_dotenv
from core import config as cfg
from core.paths import get_data_path

_ENV_PATH = get_data_path(cfg.API_SETTINGS_FILE)

PROVIDERS = {
    "volcengine": {
        "name": "火山引擎(豆包)",
        "chat_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "models": [
            "doubao-pro-32k-250815",
            "doubao-pro-128k-250815",
            "doubao-seed-1-6-vision-250815",
            "deepseek-v3-241226",
            "deepseek-r1-250120",
        ],
        "supports_vision": True,
    },
    "deepseek": {
        "name": "DeepSeek",
        "chat_url": "https://api.deepseek.com/chat/completions",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "supports_vision": False,
    },
    "qwen": {
        "name": "通义千问",
        "chat_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-vl-plus", "qwen-vl-max"],
        "supports_vision": True,
    },
    "openai": {
        "name": "ChatGPT",
        "chat_url": "https://api.openai.com/v1/chat/completions",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "supports_vision": True,
    },
}


def get_provider(key):
    return PROVIDERS.get(key)


def get_provider_list():
    return [(k, v["name"]) for k, v in PROVIDERS.items()]


def get_models(key):
    p = PROVIDERS.get(key)
    return p["models"] if p else []


def get_chat_url(key):
    p = PROVIDERS.get(key)
    return p["chat_url"] if p else ""


def _obfuscate(key):
    return base64.b64encode(key.encode()).decode()


def _deobfuscate(encoded):
    try:
        return base64.b64decode(encoded.encode()).decode()
    except Exception:
        return encoded


def load_api_settings():
    load_dotenv(_ENV_PATH, override=True)
    raw_key = os.getenv(cfg.API_KEY_KEY, "")
    return {
        "provider": os.getenv(cfg.API_PROVIDER_KEY, ""),
        "model": os.getenv(cfg.API_MODEL_KEY, ""),
        "api_key": _deobfuscate(raw_key) if raw_key else "",
    }


def save_api_settings(provider, model, api_key):
    lines = []
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    def _set(key, value):
        found = False
        for i, line in enumerate(lines):
            if line.startswith(key + "=") or line.startswith(key + " ="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}\n")

    _set(cfg.API_PROVIDER_KEY, provider)
    _set(cfg.API_MODEL_KEY, model)
    _set(cfg.API_KEY_KEY, _obfuscate(api_key))

    with open(_ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def test_connection(provider, api_key, model):
    url = get_chat_url(provider)
    if not url:
        return False, "未知厂商"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            return True, "连接成功"
        if resp.status_code == 401:
            return False, "API Key 无效"
        if resp.status_code == 404:
            msg = resp.json().get("error", {}).get("message", str(resp.status_code))
            return False, f"模型不存在: {msg}"
        msg = resp.json().get("error", {}).get("message", str(resp.status_code))
        return False, f"请求失败: {msg}"
    except requests.exceptions.Timeout:
        return False, "连接超时"
    except requests.exceptions.ConnectionError:
        return False, "无法连接服务器"
    except Exception as e:
        return False, f"错误: {e}"
