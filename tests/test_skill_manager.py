"""技能管理器：重名/缺 execute 防御 + tools/执行路由"""
import json

from core.skill_system.manager import SkillManager


class DummyPet:
    pass


def _make_skill(dirpath, name, desc, exec_body):
    d = dirpath / name
    (d / "scripts").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"""---
name: {name}
description: {desc}
---

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| x | string | 否 | 参数 |
""",
        encoding="utf-8",
    )
    (d / "scripts" / "helper.py").write_text(exec_body, encoding="utf-8")


def test_manager_skips_duplicate_and_noexec(tmp_path, monkeypatch):
    monkeypatch.setattr("core.skill_system.manager.SKILLS_DIR", str(tmp_path))
    monkeypatch.setattr("core.skill_system.manager.CONFIG_PATH", str(tmp_path / "cfg.json"))

    _make_skill(tmp_path, "good", "好技能", "def execute(x='a'):\n    return f'ok-{x}'\n")
    # 重名技能：目录名 zdup（排在 good 之后加载），SKILL.md 声明 name: good，应被跳过
    zd = tmp_path / "zdup"
    (zd / "scripts").mkdir(parents=True, exist_ok=True)
    (zd / "SKILL.md").write_text(
        "---\nname: good\ndescription: 重名技能\n---\n\n## Parameters\n\n"
        "| 参数 | 类型 | 必填 | 说明 |\n|------|------|------|------|\n"
        "| x | string | 否 | 参数 |\n",
        encoding="utf-8",
    )
    (zd / "scripts" / "helper.py").write_text(
        "def execute():\n    return 'dup'\n", encoding="utf-8"
    )
    # 无 execute 实现，应被跳过
    _make_skill(tmp_path, "noexec", "无实现", "x = 1\n")

    m = SkillManager(DummyPet())
    names = [s["name"] for s in m.list_skills()]
    assert names == ["good"], names

    tools = m.get_tools()
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "good"
    assert tools[0]["function"]["parameters"]["properties"]["x"]["type"] == "string"

    assert m.execute("good", '{"x": "b"}') == "ok-b"
    assert m.execute("unknown") == "未知技能: unknown"


def test_manager_toggle_persists(tmp_path, monkeypatch):
    monkeypatch.setattr("core.skill_system.manager.SKILLS_DIR", str(tmp_path))
    cfg_path = tmp_path / "cfg.json"
    monkeypatch.setattr("core.skill_system.manager.CONFIG_PATH", str(cfg_path))

    _make_skill(tmp_path, "good", "好技能", "def execute():\n    return 'ok'\n")
    m = SkillManager(DummyPet())
    assert m.is_enabled("good") is True
    m.toggle("good", False)
    assert m.is_enabled("good") is False
    assert json.loads(cfg_path.read_text(encoding="utf-8")) == {"good": False}
    assert m.get_tools() == []


def test_execute_error_returns_message(tmp_path, monkeypatch):
    monkeypatch.setattr("core.skill_system.manager.SKILLS_DIR", str(tmp_path))
    monkeypatch.setattr("core.skill_system.manager.CONFIG_PATH", str(tmp_path / "cfg.json"))
    _make_skill(tmp_path, "boom", "会炸", "def execute():\n    raise ValueError('boom')\n")
    m = SkillManager(DummyPet())
    result = m.execute("boom")
    assert "boom" in result
