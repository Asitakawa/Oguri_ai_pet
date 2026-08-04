"""SKILL.md 解析与 scripts 加载测试"""
from core.skill_system.loader import load_scripts, parse_frontmatter, parse_parameters

SAMPLE = """---
name: get_weather
description: 查询指定城市的当前天气
---

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| city | string | 是 | 城市名 |
| unit | string | 否 | 温度单位 |
"""


def test_parse_frontmatter_basic():
    meta, body = parse_frontmatter(SAMPLE)
    assert meta["name"] == "get_weather"
    assert meta["description"] == "查询指定城市的当前天气"
    assert "## Parameters" in body


def test_parse_frontmatter_without_frontmatter():
    meta, body = parse_frontmatter("plain text")
    assert meta == {}
    assert body == "plain text"


def test_parse_parameters_from_table():
    meta, body = parse_frontmatter(SAMPLE)
    params = parse_parameters(meta, body)
    assert len(params) == 2
    city = params[0]
    assert city["name"] == "city"
    assert city["type"] == "string"
    assert city["required"] is True
    assert params[1]["required"] is False


def test_parse_parameters_from_yaml_list():
    meta = {"parameters": [{"name": "a", "type": "string", "required": True}]}
    assert parse_parameters(meta, "body") == meta["parameters"]


def test_load_scripts_returns_execute(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "helper.py").write_text(
        "def execute(x):\n    return f'got {x}'\n", encoding="utf-8"
    )
    fn = load_scripts(str(tmp_path), "mod")
    assert callable(fn)
    assert fn(3) == "got 3"


def test_load_scripts_missing_dir(tmp_path):
    assert load_scripts(str(tmp_path), "mod") is None
