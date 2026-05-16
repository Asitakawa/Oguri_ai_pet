"""
AI 交互客户端
支持 DeepSeek / 火山引擎 / 千问 / ChatGPT 多厂商动态切换
"""
import base64
import io
import time
import random
import requests
from PIL import ImageGrab
from . import config as cfg
from .api_providers import get_chat_url, load_api_settings, get_provider


class AIClient:
    """多厂商 AI 客户端，运行时动态切换"""

    def __init__(self):
        self._reload()

    def _reload(self):
        settings = load_api_settings()
        self.provider = settings["provider"]
        self.model = settings["model"]
        self.api_key = settings["api_key"]
        self._url = get_chat_url(self.provider)
        info = get_provider(self.provider)
        self.supports_vision = info["supports_vision"] if info else True

    def switch(self, provider, model, api_key):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self._url = get_chat_url(provider)
        info = get_provider(provider)
        self.supports_vision = info["supports_vision"] if info else True

    @property
    def is_configured(self):
        return bool(self.api_key and len(self.api_key) > 10)

    def call(self, prompt, img_base64="", history_context=None,
             max_retries=3) -> str:
        if not self.is_configured:
            return None

        for attempt in range(max_retries):
            try:
                messages = [{"role": "system", "content": cfg.SYSTEM_PROMPT}]

                if history_context:
                    messages.extend([
                        {"role": m["role"], "content": m["content"]}
                        for m in history_context
                    ])

                user_content = prompt
                if img_base64 and self.supports_vision:
                    user_content = [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                    ]
                messages.append({"role": "user", "content": user_content})

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                data = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 1.0,
                    "max_tokens": 500,
                }

                timeout = 30 if img_base64 else 20
                resp = requests.post(
                    self._url, headers=headers, json=data, timeout=timeout
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
                else:
                    print(f"AI请求失败，状态码: {resp.status_code}")
                    if resp.status_code in (401, 403, 404):
                        return None

            except requests.exceptions.Timeout:
                print(f"AI调用超时（第{attempt + 1}次尝试）")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
            except requests.exceptions.ConnectionError:
                print(f"AI连接错误（第{attempt + 1}次尝试）")
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    return None
            except requests.exceptions.RequestException as e:
                print(f"AI请求异常（第{attempt + 1}次尝试）：{e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return None
            except Exception as e:
                print(f"AI调用未知异常（第{attempt + 1}次尝试）：{e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return None

        return None

    @staticmethod
    def capture_screen():
        try:
            img = ImageGrab.grab()
            img.thumbnail((1000, 750))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"截图失败：{e}")
            return None

    def ask(self, user_message, with_screenshot=False):
        img_base64 = self.capture_screen() if with_screenshot else ""

        if with_screenshot:
            prompt = (
                f"优先回答我的问题：{user_message}\n"
                "如果问题和屏幕内容相关，请结合屏幕内容回答。\n"
                "要求：小栗帽语气，体现天然呆大胃王特征，10-30字。"
            )
        else:
            prompt = (
                f"回答我的问题：{user_message}\n"
                "要求：小栗帽语气，体现天然呆大胃王特征，10-30字。"
            )

        result = self.call(prompt, img_base64)
        if result is None:
            result = random.choice(cfg.FALLBACK_AI_RESPONSES)
        return result, img_base64

    def auto_talk_prompt(self):
        img_base64 = self.capture_screen()
        prompt = "分析屏幕内容，用小栗帽的语气说一句话，体现天然呆大胃王特征"
        result = self.call(prompt, img_base64, history_context=None)
        if result is None:
            result = random.choice(cfg.FALLBACK_TALK_TEXTS)
        return result
