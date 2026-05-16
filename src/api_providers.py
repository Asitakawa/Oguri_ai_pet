"""
多厂商 API 配置预设
"""
import os
from dotenv import load_dotenv
from . import config as cfg
from .utils import get_data_path

PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "supports_vision": False,
    },
    "volcengine": {
        "name": "火山引擎 (豆包)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": [
            "doubao-seed-1-6-vision-250815",
            "doubao-lite-4k",
            "doubao-pro-32k",
            "doubao-standard-4k",
        ],
        "default_model": "doubao-seed-1-6-vision-250815",
        "supports_vision": True,
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-vl-plus", "qwen-vl-max"],
        "default_model": "qwen-plus",
        "supports_vision": True,
    },
    "chatgpt": {
        "name": "ChatGPT (OpenAI)",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "default_model": "gpt-4o-mini",
        "supports_vision": True,
    },
}

_ENV_PATH = get_data_path(cfg.API_SETTINGS_FILE)


def get_provider(provider_id):
    return PROVIDERS.get(provider_id)


def get_provider_list():
    return [(k, v["name"]) for k, v in PROVIDERS.items()]


def get_models(provider_id):
    p = PROVIDERS.get(provider_id)
    return p["models"] if p else []


def get_chat_url(provider_id):
    p = PROVIDERS.get(provider_id)
    return f"{p['base_url']}/chat/completions" if p else ""


def load_api_settings():
    load_dotenv(_ENV_PATH, override=True)
    return {
        "provider": os.getenv(cfg.API_PROVIDER_KEY, "volcengine"),
        "model": os.getenv(cfg.API_MODEL_KEY, "doubao-seed-1-6-vision-250815"),
        "api_key": os.getenv(cfg.API_KEY_KEY, ""),
    }


def save_api_settings(provider, model, api_key):
    """保存 API 配置到 .env（手动写文件，避免 dotenv.set_key 格式问题）"""
    lines = []
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    def _set_or_append(key, value):
        found = False
        for i, line in enumerate(lines):
            if line.startswith(key + '=') or line.startswith(key + ' ='):
                lines[i] = f"{key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}\n")

    _set_or_append(cfg.API_PROVIDER_KEY, provider)
    _set_or_append(cfg.API_MODEL_KEY, model)
    _set_or_append(cfg.API_KEY_KEY, api_key)

    with open(_ENV_PATH, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def test_connection(provider_id, api_key, model):
    """测试 API 连接是否可用"""
    import requests
    url = get_chat_url(provider_id)
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
            return True, "连接成功 ✅"
        elif resp.status_code == 401:
            return False, "API Key 无效 ❌"
        elif resp.status_code == 404:
            return False, "模型不存在 ❌"
        else:
            msg = resp.json().get("error", {}).get("message", str(resp.status_code))
            return False, f"请求失败: {msg}"
    except requests.exceptions.Timeout:
        return False, "连接超时 ⏱"
    except requests.exceptions.ConnectionError:
        return False, "无法连接服务器 🔌"
    except Exception as e:
        return False, f"错误: {e}"
