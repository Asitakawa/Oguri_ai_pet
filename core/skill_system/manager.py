"""技能管理器"""
import importlib.util
import inspect
import json
import os
import shutil
import sys
import threading

from utils.paths import get_resource_path, get_data_path
from core.skill_system.loader import parse_frontmatter, parse_parameters, load_main

SKILLS_DIR = get_resource_path("skills")
CONFIG_PATH = get_data_path("skills_config.json")

_TYPE_MAP = {int: "integer", float: "number", bool: "boolean", str: "string"}


class SkillManager:
    def __init__(self, pet):
        self.pet = pet
        self._lock = threading.Lock()
        self._skills = {}
        self._config = self._load_config()
        self._load_all()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"技能配置保存失败: {e}")

    def _load_all(self):
        with self._lock:
            self._skills.clear()
        if not os.path.isdir(SKILLS_DIR):
            return
        for entry in sorted(os.listdir(SKILLS_DIR)):
            skill_dir = os.path.join(SKILLS_DIR, entry)
            md_path = os.path.join(skill_dir, "SKILL.md")
            if os.path.isdir(skill_dir) and os.path.isfile(md_path):
                self._load_one(entry, skill_dir, md_path)

    def _load_one(self, dirname, skill_dir, md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except IOError:
            return
        fm, body = parse_frontmatter(raw)
        name = fm.get("name") or dirname
        desc = fm.get("description", "")
        params = parse_parameters(fm, body)
        py_path = os.path.join(skill_dir, "main.py")
        execute_fn = load_main(py_path, f"skill_{name}")
        with self._lock:
            self._skills[name] = {
                "name": name,
                "description": desc,
                "parameters": params,
                "execute_fn": execute_fn,
                "dirname": dirname,
            }

    def is_enabled(self, name):
        with self._lock:
            return self._config.get(name, True)

    def toggle(self, name, enabled):
        with self._lock:
            self._config[name] = enabled
        self._save_config()

    def get_tools(self):
        tools = []
        with self._lock:
            items = list(self._skills.items())
        for name, sk in items:
            if not sk["execute_fn"] or not self._config.get(name, True):
                continue
            props = {}
            required = []
            for p in sk["parameters"]:
                props[p["name"]] = {
                    "type": _TYPE_MAP.get(p.get("type", str), "string"),
                    "description": p.get("description", ""),
                }
                if p.get("required"):
                    required.append(p["name"])
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": sk["description"],
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            })
        return tools

    def execute(self, name, arguments: str = "{}"):
        with self._lock:
            if name not in self._skills:
                return f"未知技能: {name}"
            sk = self._skills[name]
        if not sk["execute_fn"]:
            return f"技能 {name} 没有后端实现"
        try:
            kwargs = json.loads(arguments) if isinstance(arguments, str) else arguments
            sig = inspect.signature(sk["execute_fn"])
            filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
            if "_pet" in sig.parameters:
                filtered["_pet"] = self.pet
            result = sk["execute_fn"](**filtered)
            return str(result) if result is not None else ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"技能执行错误: {e}"

    def list_skills(self):
        with self._lock:
            return [
                {"name": s["name"], "description": s["description"],
                 "enabled": self._config.get(s["name"], True)}
                for s in self._skills.values()
            ]

    def remove_skill(self, name):
        with self._lock:
            if name not in self._skills:
                return False
            d = self._skills[name]["dirname"]
            path = os.path.join(SKILLS_DIR, d)
        try:
            shutil.rmtree(path)
            with self._lock:
                self._skills.pop(name, None)
                self._config.pop(name, None)
            self._save_config()
            return True
        except OSError as e:
            print(f"删除技能失败: {e}")
            return False

    def add_skill(self, source_path):
        if not os.path.isfile(source_path) or not source_path.endswith(".py"):
            return False, "仅支持 .py 文件"
        base = os.path.splitext(os.path.basename(source_path))[0]
        target_dir = os.path.join(SKILLS_DIR, base)
        if os.path.exists(target_dir):
            return False, f"技能 {base} 已存在"
        try:
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(source_path, os.path.join(target_dir, "main.py"))
            name_hint = os.path.splitext(os.path.basename(source_path))[0]

            param_rows = ""
            try:
                spec = importlib.util.spec_from_file_location(f"_import_{name_hint}", source_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[f"_import_{name_hint}"] = mod
                    spec.loader.exec_module(mod)
                    fn = getattr(mod, "execute", None)
                    if fn:
                        sig = inspect.signature(fn)
                        for pname, p in sig.parameters.items():
                            if pname == "_pet":
                                continue
                            ptype = _TYPE_MAP.get(p.annotation if p.annotation is not inspect.Parameter.empty else str, "string")
                            pdesc = pname
                            preq = "是" if p.default is inspect.Parameter.empty else "否"
                            param_rows += f"| {pname} | {ptype} | {preq} | {pdesc} |\n"
            except Exception:
                param_rows = ""
            if not param_rows:
                param_rows = "| input | string | 否 | 输入内容 |\n"

            sk_md = f"""---
name: {name_hint}
description: 外部导入的技能
---

# {name_hint}

## Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
{param_rows}"""
            with open(os.path.join(target_dir, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(sk_md)
            self._load_all()
            return True, f"技能 {name_hint} 添加成功"
        except OSError as e:
            return False, f"添加失败: {e}"
