"""AI 交互客户端 — 多厂商 + Function Calling"""
import base64
import io
import json
import time
import random
import requests
from PIL import ImageGrab
from core import config as cfg
from ai.providers import get_chat_url, load_api_settings, get_provider


class AIClient:
    def __init__(self):
        self._reload()

    def _reload(self):
        s = load_api_settings()
        self.provider = s["provider"]
        self.model = s["model"]
        self.api_key = s["api_key"]
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

    def _post(self, data, timeout):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(self._url, headers=headers, json=data, timeout=timeout)
        if resp.status_code != 200:
            print(f"AI请求失败，状态码: {resp.status_code}")
            return None
        return resp.json()

    def call(self, prompt, img_base64="", history_context=None,
             max_retries=2, tools=None, execute_tool=None) -> str:
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
                uc = prompt
                if img_base64 and self.supports_vision:
                    uc = [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                    ]
                messages.append({"role": "user", "content": uc})

                data = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 1.0,
                    "max_tokens": 2000 if tools else 500,
                }
                if tools:
                    data["tools"] = tools
                    data["tool_choice"] = "auto"

                timeout = 60 if img_base64 or tools else 30
                result = self._post(data, timeout)
                if result is None:
                    continue

                choice = result["choices"][0]
                msg = choice["message"]
                finish = choice.get("finish_reason")

                if finish == "tool_calls" and msg.get("tool_calls") and execute_tool:
                    messages.append(msg)
                    for tc in msg["tool_calls"]:
                        tr = execute_tool(tc["function"]["name"], tc["function"]["arguments"])
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tr,
                        })
                    data["messages"] = messages
                    data.pop("tool_choice", None)
                    for _ in range(5):
                        second = self._post(data, timeout)
                        if not second:
                            break
                        smsg = second["choices"][0]["message"]
                        if smsg.get("content"):
                            return smsg["content"].strip()
                        if not smsg.get("tool_calls"):
                            return "处理完成にゃ～"
                        messages.append(smsg)
                        for tc in smsg["tool_calls"]:
                            tr = execute_tool(tc["function"]["name"], tc["function"]["arguments"])
                            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tr})
                        data["messages"] = messages
                    continue

                return (msg.get("content") or "处理完成にゃ～").strip()

            except requests.exceptions.Timeout:
                print(f"AI超时（第{attempt + 1}次）")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
            except requests.exceptions.ConnectionError:
                print(f"AI连接错误（第{attempt + 1}次）")
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    return None
            except Exception as e:
                print(f"AI异常（第{attempt + 1}次）: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
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
            print(f"截图失败: {e}")
            return None

    _PERSONALITY = (
        "回复要像小栗帽本人说话：\n"
        "- 天然呆 + 大胃王性格（迷糊贪吃那种）\n"
        "- 短句、口语、像搭档在耳边碎嘴\n"
        "- 不堆格式、不念稿、不端架子\n"
        "- 该有温度时有温度（鼓励、安抚），该吐槽时吐槽\n"
        "- 偶尔冒出吃的、跑步相关的联想是加分项\n"
        "字数 10-30 字，超出就砍。"
    )

    def ask(self, user_message, with_screenshot=False, history_context=None,
            tools=None, execute_tool=None):
        img_base64 = self.capture_screen() if with_screenshot else ""

        extra = "屏幕内容已截取，请结合屏幕回答；如果问题与屏幕无关，就别硬扯。\n" if with_screenshot else ""
        prompt = f"用户问：{user_message}\n{extra}{self._PERSONALITY}"

        result = self.call(prompt, img_base64, history_context=history_context,
                          tools=tools, execute_tool=execute_tool)
        if result is None:
            result = random.choice(cfg.FALLBACK_AI_RESPONSES)
        return result, img_base64

    def auto_talk_prompt(self):
        img_base64 = self.capture_screen()
        prompt = f"小栗帽想和训练员说说话：\n{self._PERSONALITY}"
        result = self.call(prompt, img_base64, history_context=None)
        if result is None:
            result = random.choice(cfg.FALLBACK_TALK_TEXTS)
        return result
