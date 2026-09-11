"""长期记忆：事实库、注入、提取解析

这一层决定「她记得你什么」，同时也是隐私敏感的持久化数据，
所以要覆盖：增删改查、上限、去重、开关、注入格式、
以及模型输出不守格式时的解析健壮性。
"""
from __future__ import annotations

import json

import pytest

from core import memory_facts as mf
from core.memory_facts import FactExtractor, MemoryFacts, parse_facts


@pytest.fixture
def facts(tmp_path):
    return MemoryFacts(str(tmp_path / "facts.json"))


# ── 基本读写 ────────────────────────────
def test_starts_empty_and_enabled(facts):
    assert len(facts) == 0
    assert facts.enabled is True
    assert facts.prompt_block() == ""


def test_add_and_persist(tmp_path):
    path = str(tmp_path / "facts.json")
    m = MemoryFacts(path)
    m.add("训练员叫小林")
    m.add("习惯凌晨两点才睡")
    m2 = MemoryFacts(path)
    assert [f["text"] for f in m2.list_all()] == ["训练员叫小林", "习惯凌晨两点才睡"]


def test_add_rejects_empty(facts):
    assert facts.add("") is None
    assert facts.add("   ") is None
    assert len(facts) == 0


def test_add_deduplicates(facts):
    assert facts.add("训练员叫小林") is not None
    assert facts.add("训练员叫小林") is None, "重复内容不应再存一条"
    assert len(facts) == 1


def test_add_truncates_long_text(facts):
    facts.add("啊" * 500)
    assert len(facts.list_all()[0]["text"]) == mf.MAX_FACT_CHARS


def test_add_strips_whitespace(facts):
    facts.add("  训练员叫小林  ")
    assert facts.list_all()[0]["text"] == "训练员叫小林"


def test_fact_has_id_and_timestamp(facts):
    f = facts.add("x")
    assert f["id"] and f["created_at"]
    assert f["source"] == "chat"


def test_remove(facts):
    a = facts.add("A")
    facts.add("B")
    assert facts.remove(a["id"]) is True
    assert [f["text"] for f in facts.list_all()] == ["B"]
    assert facts.remove("nonexistent") is False


def test_clear_returns_count(facts):
    facts.add("A")
    facts.add("B")
    assert facts.clear() == 2
    assert len(facts) == 0


def test_cap_keeps_newest(facts):
    for i in range(mf.MAX_FACTS + 20):
        facts.add(f"事实{i}")
    assert len(facts) == mf.MAX_FACTS
    assert facts.list_all()[-1]["text"] == f"事实{mf.MAX_FACTS + 19}"
    assert facts.list_all()[0]["text"] == "事实20"


def test_survives_corrupt_file(tmp_path):
    path = tmp_path / "facts.json"
    path.write_text("{{{ not json", encoding="utf-8")
    m = MemoryFacts(str(path))
    assert len(m) == 0
    m.add("A")
    assert MemoryFacts(str(path)).list_all()[0]["text"] == "A"


def test_survives_wrong_shape(tmp_path):
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"facts": [1, "x", {"no_text": 1}, {"text": "ok"}]}),
                    encoding="utf-8")
    m = MemoryFacts(str(path))
    assert [f["text"] for f in m.list_all()] == ["ok"]


def test_atomic_write_leaves_no_temp(tmp_path):
    m = MemoryFacts(str(tmp_path / "facts.json"))
    m.add("A")
    assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []


# ── 开关 ────────────────────────────────
def test_disabled_blocks_injection(facts):
    facts.add("训练员叫小林")
    assert facts.prompt_block() != ""
    facts.set_enabled(False)
    assert facts.prompt_block() == ""
    facts.set_enabled(True)
    assert facts.prompt_block() != ""


def test_enabled_persists(tmp_path):
    path = str(tmp_path / "facts.json")
    MemoryFacts(path).set_enabled(False)
    assert MemoryFacts(path).enabled is False


def test_disabled_blocks_extraction(facts):
    class DummyAI:
        def call(self, *a, **k):
            raise AssertionError("关闭后不应调用模型")

    class DummyHistory:
        history = [{"role": "user", "content": "x"}] * 100

    facts.set_enabled(False)
    ex = FactExtractor(DummyAI(), DummyHistory(), facts, min_new_messages=1)
    assert ex.should_extract() is False
    assert ex.extract_once() == 0


# ── 注入格式 ────────────────────────────
def test_prompt_block_lists_facts(facts):
    facts.add("训练员叫小林")
    facts.add("在做桌宠项目")
    block = facts.prompt_block()
    assert "训练员叫小林" in block
    assert "在做桌宠项目" in block
    assert block.startswith("━━━")


def test_prompt_block_mentions_not_to_fabricate(facts):
    facts.add("A")
    assert "不要假装记得" in facts.prompt_block()


# ── 解析模型输出 ────────────────────────
@pytest.mark.parametrize("raw,expect", [
    ("- 训练员叫小林\n- 习惯凌晨两点睡", ["训练员叫小林", "习惯凌晨两点睡"]),
    ("* 喜欢拉面", ["喜欢拉面"]),
    ("• 养了猫", ["养了猫"]),
    ("1. 喜欢拉面\n2. 在做桌宠项目", ["喜欢拉面", "在做桌宠项目"]),
    ("- 无", []),
    ("- （无）", []),
    ("- 没有值得记的", []),
    ("", []),
    (None, []),
])
def test_parse_facts_formats(raw, expect):
    assert parse_facts(raw) == expect


def test_parse_facts_drops_headings_and_meta():
    raw = "**关于训练员**\n# 长期记忆\n以下是提取的事实：\n- 在做桌宠项目"
    assert parse_facts(raw) == ["在做桌宠项目"]


def test_parse_facts_caps_length():
    long = "- " + "啊" * 500
    assert len(parse_facts(long)[0]) == mf.MAX_FACT_CHARS


def test_parse_facts_keeps_multiple_distinct():
    raw = "- A\n- B\n- C"
    assert parse_facts(raw) == ["A", "B", "C"]


# ── 提取器 ──────────────────────────────
class FakeHistory:
    def __init__(self, n):
        self.history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
            for i in range(n)
        ]

    def __len__(self):
        return len(self.history)

    def get_context(self, size=100):
        return list(self.history[-size:])


class FakeAI:
    def __init__(self, reply="- 训练员在做桌宠项目"):
        self.reply = reply
        self.calls = 0

    def call(self, *a, **k):
        self.calls += 1
        return self.reply


def test_extractor_waits_for_enough_messages(facts):
    ex = FactExtractor(FakeAI(), FakeHistory(3), facts, min_new_messages=10)
    assert ex.should_extract() is False
    assert ex.extract_once() == 0
    assert len(facts) == 0


def test_extractor_runs_when_threshold_reached(facts):
    ai = FakeAI("- 训练员在做桌宠项目\n- 训练员养了猫")
    hist = FakeHistory(20)
    ex = FactExtractor(ai, hist, facts, min_new_messages=10)
    assert ex.should_extract() is True
    assert ex.extract_once() == 2
    assert ai.calls == 1
    assert {f["text"] for f in facts.list_all()} == {"训练员在做桌宠项目", "训练员养了猫"}


def test_extractor_does_not_reread_same_messages(facts):
    ai = FakeAI("- A")
    hist = FakeHistory(20)
    ex = FactExtractor(ai, hist, facts, min_new_messages=10)
    ex.extract_once()
    assert ex.should_extract() is False, "游标应推进，避免重复提取同一段"
    ex.extract_once()
    assert ai.calls == 1
    hist.history.extend([{"role": "user", "content": "new"}] * 12)
    assert ex.should_extract() is True


def test_extractor_handles_ai_failure(facts):
    class BoomAI:
        def call(self, *a, **k):
            raise RuntimeError("网络炸了")

    ex = FactExtractor(BoomAI(), FakeHistory(30), facts, min_new_messages=5)
    assert ex.extract_once() == 0, "失败不应抛异常"
    assert len(facts) == 0


def test_extractor_handles_empty_reply(facts):
    ex = FactExtractor(FakeAI(""), FakeHistory(30), facts, min_new_messages=5)
    assert ex.extract_once() == 0


def test_extractor_counts_companion_facts(tmp_path):
    from core.companion import CompanionStats

    c = CompanionStats(str(tmp_path / "companion.json"))
    facts = MemoryFacts(str(tmp_path / "facts.json"), companion=c)
    ex = FactExtractor(FakeAI("- A\n- B"), FakeHistory(30), facts, min_new_messages=5)
    ex.extract_once()
    assert c.snapshot()["facts_learned"] == 2


def test_reset_cursor(facts):
    hist = FakeHistory(30)
    ex = FactExtractor(FakeAI("- A"), hist, facts, min_new_messages=5)
    ex.reset_cursor()
    assert ex.should_extract() is False
