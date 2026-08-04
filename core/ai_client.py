"""AI 交互客户端 — 多厂商 + Function Calling（合并新版实现）"""
from __future__ import annotations

import base64
import io
import random
import time
from typing import Callable, Dict, List, Optional

import requests
from PIL import ImageGrab

from core import config as cfg
from core.ai_providers import get_chat_url, get_provider, load_api_settings
from utils.logger import get_logger

log = get_logger("ai_client")

# 短句回复约束（人格主体在 config.SYSTEM_PROMPT，这里补充语气与长度约束）
_PERSONALITY = (
    "回复要像小栗帽本人说话：\n"
    "- 天然呆 + 大胃王性格（迷糊贪吃那种）\n"
    "- 短句、口语、像搭档在耳边碎嘴\n"
    "- 不堆格式、不念稿、不端架子\n"
    "- 该有温度时有温度（鼓励、安抚），该吐槽时吐槽\n"
    "- 偶尔冒出吃的、跑步相关的联想是加分项\n"
    "字数 10-30 字，超出就砍。"
)


class AIClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._reload()

    def _reload(self) -> None:
        s = load_api_settings()
        self.provider: str = s["provider"]
        self.model: str = s["model"]
        self.api_key: str = s["api_key"]
        self._url: str = get_chat_url(self.provider)
        info = get_provider(self.provider)
        self.supports_vision: bool = bool(info and info.get("supports_vision", True))

    def switch(self, provider: str, model: str, api_key: str) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self._url = get_chat_url(provider)
        info = get_provider(provider)
        self.supports_vision = bool(info and info.get("supports_vision", True))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def _post(self, data: Dict, timeout: tuple) -> Optional[Dict]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = self._session.post(self._url, headers=headers, json=data, timeout=timeout)
        if resp.status_code != 200:
            log.warning("AI请求失败，状态码: %s", resp.status_code)
            return None
        try:
            return resp.json()
        except ValueError:
            log.error("AI返回非 JSON 内容")
            return None

    def call(self, prompt: str, img_base64: str = "",
             history_context: Optional[List[dict]] = None, max_retries: int = 2,
             tools: Optional[List[dict]] = None,
             execute_tool: Optional[Callable] = None) -> Optional[str]:
        if not self.is_configured:
            return None

        for attempt in range(max_retries):
            try:
                messages: List[dict] = [{"role": "system", "content": cfg.SYSTEM_PROMPT}]
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

                data: Dict = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 1.0,
                    "max_tokens": 2000 if tools else 500,
                }
                if tools:
                    data["tools"] = tools
                    data["tool_choice"] = "auto"

                tout = (15, 120) if tools else ((15, 60) if img_base64 else (10, 30))
                result = self._post(data, tout)
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
                        second = self._post(data, tout)
                        if not second:
                            break
                        smsg = second["choices"][0]["message"]
                        if smsg.get("content"):
                            return smsg["content"].strip()
                        if not smsg.get("tool_calls"):
                            return "处理完成了"
                        messages.append(smsg)
                        for tc in smsg["tool_calls"]:
                            tr = execute_tool(tc["function"]["name"], tc["function"]["arguments"])
                            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tr})
                        data["messages"] = messages
                    continue

                return (msg.get("content") or "处理完成了").strip()

            except requests.exceptions.Timeout:
                log.warning("AI超时（第%d次）", attempt + 1)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None
            except requests.exceptions.ConnectionError:
                log.warning("AI连接错误（第%d次）", attempt + 1)
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    return None
            except Exception:
                log.exception("AI异常（第%d次）", attempt + 1)
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return None
        return None

    @staticmethod
    def capture_screen() -> Optional[str]:
        try:
            img = ImageGrab.grab()
            img.thumbnail((640, 480))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=25)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            log.warning("截图失败", exc_info=True)
            return None

    def ask(self, user_message: str, with_screenshot: bool = False,
            history_context: Optional[List[dict]] = None,
            tools: Optional[List[dict]] = None,
            execute_tool: Optional[Callable] = None):
        img_base64 = self.capture_screen() if with_screenshot else ""

        extra = "屏幕内容已截取，请结合屏幕回答；如果问题与屏幕无关，就别硬扯。\n" if with_screenshot else ""
        if user_message:
            prompt = f"用户问：{user_message}\n{extra}{_PERSONALITY}"
        else:
            prompt = f"看看屏幕\n{extra}{_PERSONALITY}"

        result = self.call(prompt, img_base64, history_context=history_context,
                          tools=tools, execute_tool=execute_tool)
        if result is None:
            result = random.choice(cfg.FALLBACK_AI_RESPONSES)
        return result, img_base64

    def auto_talk_prompt(self, history_context: Optional[List[dict]] = None) -> str:
        img_base64 = self.capture_screen()
        prompt = f"小栗帽想和训练员说说话：\n{_PERSONALITY}"
        result = self.call(prompt, img_base64, history_context=history_context)
        if result is None:
            result = random.choice(cfg.FALLBACK_TALK_TEXTS)
        return result
