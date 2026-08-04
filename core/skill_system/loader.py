"""SKILL.md 解析 + scripts/ 动态加载"""
from __future__ import annotations

import importlib.util
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

from utils.logger import get_logger

log = get_logger("skill_loader")


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    data: Dict[str, str] = {}
    ck = None
    cv = []
    ml = False
    for line in lines[1:end]:
        if ml:
            if line and line[0] in (" ", "\t"):
                cv.append(line.strip())
                continue
            data[ck] = "\n".join(cv)  # type: ignore[index]
            ml = False
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v == "|":
            ml = True
            ck = k
            cv = []
        elif v:
            data[k] = v
    if ml:
        data[ck] = "\n".join(cv)  # type: ignore[index]
    return data, "\n".join(lines[end + 1:])


def parse_parameters(frontmatter: Dict[str, str], body: str) -> List[dict]:
    params: List[dict] = []
    if "parameters" in frontmatter:
        raw = frontmatter["parameters"]
        if isinstance(raw, list):
            return raw
    in_table = False
    for line in body.split("\n"):
        if line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if not in_table:
                in_table = True
            else:
                if len(cells) >= 3:
                    params.append({
                        "name": cells[0],
                        "type": cells[1],
                        "required": cells[2] == "是",
                        "description": cells[3] if len(cells) > 3 else "",
                    })
        elif in_table and not line.startswith("|"):
            break
    return params


def load_scripts(skill_dir: str, mod_name: str) -> Optional[Callable]:
    """加载技能目录下的 scripts/ 中的 Python 文件，返回 execute 函数"""
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return None
    for fname in sorted(os.listdir(scripts_dir)):
        if fname.endswith(".py"):
            py_path = os.path.join(scripts_dir, fname)
            try:
                spec = importlib.util.spec_from_file_location(
                    f"{mod_name}_{fname[:-3]}", py_path)
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[f"{mod_name}_{fname[:-3]}"] = mod
                spec.loader.exec_module(mod)
                execute = getattr(mod, "execute", None)
                if execute:
                    return execute
            except Exception as e:
                log.warning("技能脚本加载失败 %s: %s", fname, e)
    return None
