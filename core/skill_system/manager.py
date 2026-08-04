"""技能管理器"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import shutil
import sys
import threading
import zipfile

from core.paths import get_data_path, get_resource_path
from core.skill_system.loader import load_scripts, parse_frontmatter, parse_parameters
from utils.logger import get_logger

log = get_logger("skill_manager")

SKILLS_DIR = get_resource_path("skills")
CONFIG_PATH = get_data_path("skills_config.json")

_TYPE_MAP = {int: "integer", float: "number", bool: "boolean", str: "string"}


class SkillManager:
    def __init__(self, pet) -> None:
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
            log.warning("技能配置保存失败: %s", e)

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
        execute_fn = load_scripts(skill_dir, f"skill_{name}")
        with self._lock:
            if name in self._skills:
                log.warning("跳过技能 %s（目录 %s）：与已有技能重名", name, dirname)
                return
        if execute_fn is None:
            log.warning("跳过技能 %s（目录 %s）：缺少可执行的 execute 实现", name, dirname)
            return
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
            log.exception("技能执行错误: %s", e)
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
            log.warning("删除技能失败: %s", e)
            return False

    def add_skill_zip(self, zip_path):
        if not os.path.isfile(zip_path) or not zip_path.endswith(".zip"):
            return False, "仅支持 .zip 文件"
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.namelist()
                if not members:
                    return False, "压缩包为空"
                top = members[0].split("/")[0]
                md_path = f"{top}/SKILL.md"
                if md_path not in members:
                    return False, "压缩包内未找到 SKILL.md"
                target_dir = os.path.join(SKILLS_DIR, top)
                if os.path.exists(target_dir):
                    return False, f"技能 {top} 已存在"
                zf.extractall(SKILLS_DIR)
            self._load_all()
            return True, f"技能 {top} 添加成功"
        except (zipfile.BadZipFile, OSError) as e:
            return False, f"解压失败: {e}"

    def add_skill(self, source_path):
        if not os.path.isfile(source_path) or not source_path.endswith(".py"):
            return False, "仅支持 .py 文件"
        base = os.path.splitext(os.path.basename(source_path))[0]
        target_dir = os.path.join(SKILLS_DIR, base)
        if os.path.exists(target_dir):
            return False, f"技能 {base} 已存在"
        try:
            os.makedirs(os.path.join(target_dir, "scripts"), exist_ok=True)
            shutil.copy2(source_path, os.path.join(target_dir, "scripts", "helper.py"))
            name_hint = os.path.splitext(os.path.basename(source_path))[0]

            param_rows = ""
            skill_name = name_hint
            skill_desc = "外部导入的技能"
            try:
                spec = importlib.util.spec_from_file_location(f"_import_{name_hint}", source_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[f"_import_{name_hint}"] = mod
                    spec.loader.exec_module(mod)
                    skill_name = getattr(mod, "NAME", name_hint)
                    skill_desc = getattr(mod, "DESCRIPTION", "外部导入的技能")
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
name: {skill_name}
description: {skill_desc}
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
