"""长期记忆 — 把聊天记录压缩成关于训练员的事实

为什么需要它：`chat_history.json` 是滑动窗口，超出 `MEMORY_CONTEXT_SIZE`
的对话会被永久丢弃，于是「第七天和第一天体验一样」。这里把历史对话定期
压缩成短小、稳定的事实，注入 system prompt，让跨会话的记忆真正积累。

隐私边界（重要）：
- 全部存在本地数据目录的 `facts.json`，不上传到任何地方，除了随对话一起
  发给用户自己配置的模型厂商
- 面板里可逐条查看、逐条删除、一键清空
- 可在设置里整体关闭（`enabled=False` 后既不再提取也不注入）
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from typing import List, Optional

from core.paths import get_data_path
from utils.logger import get_logger

log = get_logger("memory_facts")

FILE_NAME = "facts.json"
MAX_FACTS = 40          # 注入上下文的上限，超了就丢最旧的
MAX_FACT_CHARS = 60     # 单条fact 的长度上限，防止模型写小作文
DEFAULT_ENABLED = True


def _atomic_write(path: str, data) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


class MemoryFacts:
    """线程安全的事实库。"""

    def __init__(self, path: Optional[str] = None, companion=None) -> None:
        self._path = path or get_data_path(FILE_NAME)
        self._lock = threading.Lock()
        self._companion = companion
        self._facts: List[dict] = []
        self._enabled: bool = DEFAULT_ENABLED
        self._load()

    # ── 持久化 ────────────────────────────
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            return
        except Exception as e:
            log.warning("长期记忆读取失败: %s", e)
            return
        if not isinstance(raw, dict):
            return
        self._enabled = bool(raw.get("enabled", DEFAULT_ENABLED))
        items = raw.get("facts")
        if isinstance(items, list):
            self._facts = [f for f in items if isinstance(f, dict) and f.get("text")]

    def save(self) -> None:
        with self._lock:
            snap = {"enabled": self._enabled, "facts": list(self._facts)}
        try:
            _atomic_write(self._path, snap)
        except OSError as e:
            log.warning("长期记忆保存失败: %s", e)

    # ── 开关 ──────────────────────────────
    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, value: bool) -> None:
        with self._lock:
            self._enabled = bool(value)
        self.save()

    # ── 读写 ──────────────────────────────
    def add(self, text: str, source: str = "chat") -> Optional[dict]:
        """加入一条事实。重复内容会被跳过（返回 None）。"""
        text = (text or "").strip()
        if not text:
            return None
        text = text[:MAX_FACT_CHARS]
        with self._lock:
            if any(f["text"] == text for f in self._facts):
                return None
            fact = {
                "id": uuid.uuid4().hex[:10],
                "text": text,
                "source": source,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            }
            self._facts.append(fact)
            dropped = 0
            while len(self._facts) > MAX_FACTS:
                self._facts.pop(0)
                dropped += 1
        self.save()
        if self._companion is not None and dropped == 0:
            try:
                self._companion.bump("facts_learned")
            except Exception:
                pass
        return fact

    def list_all(self) -> List[dict]:
        with self._lock:
            return list(self._facts)

    def remove(self, fact_id: str) -> bool:
        with self._lock:
            before = len(self._facts)
            self._facts = [f for f in self._facts if f["id"] != fact_id]
            removed = len(self._facts) != before
        if removed:
            self.save()
        return removed

    def clear(self) -> int:
        with self._lock:
            n = len(self._facts)
            self._facts = []
        self.save()
        return n

    def __len__(self) -> int:
        with self._lock:
            return len(self._facts)

    # ── 注入 ──────────────────────────────
    def prompt_block(self) -> str:
        """拼成给 system prompt 用的一段。关闭或无内容时返回空串。"""
        if not self.enabled:
            return ""
        facts = self.list_all()
        if not facts:
            return ""
        lines = "\n".join(f"- {f['text']}" for f in facts)
        return (
            "━━━ 你记得的训练员 ━━━\n"
            "以下是你长期相处中记住的事，回答时可以自然地用上，"
            "但不要生硬地逐条复述，也不要假装记得没写在下面的事：\n"
            f"{lines}\n"
        )


# ── 提取 ──────────────────────────────────
_EXTRACT_PROMPT = (
    "下面是小栗帽（桌面宠物）和训练员的对话记录。\n"
    "请提取**关于训练员本人**的、值得长期记住的事实，例如：称呼、作息习惯、"
    "在做的工作或项目、喜好、反复提到的人或事、明确说过的偏好。\n"
    "\n"
    "要求：\n"
    "- 每条一行，以「- 」开头，不超过 25 个字\n"
    "- 只写稳定的事实，不要写一次性事件、不要写寒暄、不要复述小栗帽说过的话\n"
    "- 没有值得记的就只输出一行「- 无」\n"
    "- 不要输出任何解释或标题\n"
    "\n"
    "对话记录：\n"
)


def parse_facts(raw: str) -> List[str]:
    """从模型输出里解析出事实条目。

    模型经常不守格式，所以这里既做兼容也做过滤：小标题、加粗行、问句式的
    自我说明都不要，否则会被当成「记得训练员的事」注入进去。
    """
    if not raw:
        return []
    out: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 容忍 "- x" / "* x" / "• x" / "1. x" 等写法
        for prefix in ("- ", "* ", "• "):
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        else:
            head, sep, rest = line.partition(". ")
            if sep and head.isdigit():
                line = rest.strip()
        line = line.strip().strip("「」\"'")
        if not line or line in ("无", "（无）", "(无)", "没有", "暂无"):
            continue
        # 小标题 / 表头：Markdown 强调、或以冒号结尾的短行
        stripped = line.strip("*_#` ")
        if line.startswith(("**", "#")) or stripped.endswith(("：", ":")):
            continue
        # 元叙述（模型在解释自己要做什么），不是关于训练员的事实
        if any(k in line for k in ("以下是", "没有值得记", "不值得记", "无需记录")):
            continue
        line = stripped
        if not line:
            continue
        if len(line) > MAX_FACT_CHARS:
            line = line[:MAX_FACT_CHARS]
        out.append(line)
    return out


class FactExtractor:
    """按累积消息数触发一次提取。"""

    def __init__(self, ai_client, chat_history, facts: MemoryFacts,
                 min_new_messages: int = 12, cursor: int = 0) -> None:
        self.ai = ai_client
        self.chat_history = chat_history
        self.facts = facts
        self.min_new_messages = min_new_messages
        # 游标从 0 开始：启动时若已有足够的历史（例如上次没来得及提炼），
        # 第一次检查就该把它消化掉，而不是永远等"新"消息
        self._cursor = max(0, cursor)
        self._lock = threading.Lock()

    def note_activity(self) -> None:
        """有新的对话产生时调用（只更新时间戳，不做重活）。"""
        pass

    def should_extract(self) -> bool:
        if not self.facts.enabled:
            return False
        try:
            return (len(self.chat_history) - self._cursor) >= self.min_new_messages
        except Exception:
            return False

    def extract_once(self) -> int:
        """跑一次提取，返回新增条数。失败返回 0（不抛异常）。"""
        if not self.facts.enabled:
            return 0
        with self._lock:
            messages = self.chat_history.history
            new = messages[self._cursor:]
            if len(new) < self.min_new_messages:
                return 0
            self._cursor = len(messages)

        convo = "\n".join(
            f"{'训练员' if m.get('role') == 'user' else '小栗帽'}：{m.get('content', '')}"
            for m in new
        )
        try:
            raw = self.ai.call(_EXTRACT_PROMPT + convo, max_retries=1)
        except Exception:
            log.exception("长期记忆提取调用失败")
            return 0
        if not raw:
            return 0
        added = 0
        for text in parse_facts(raw):
            if self.facts.add(text, source="chat") is not None:
                added += 1
        if added:
            log.info("长期记忆新增 %d 条（共 %d 条）", added, len(self.facts))
        return added

    def reset_cursor(self) -> None:
        with self._lock:
            self._cursor = len(self.chat_history)
