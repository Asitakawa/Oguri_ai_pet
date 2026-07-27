"""SKILL.md 解析 + main.py 动态加载"""
import importlib.util
import os
import sys


def parse_frontmatter(text):
    """解析 SKILL.md 中 --- 包裹的 YAML 前端数据"""
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

    data = {}
    ck = None
    cv = []
    ml = False

    for line in lines[1:end]:
        if ml:
            if line and line[0] in (" ", "\t"):
                cv.append(line.strip())
                continue
            data[ck] = "\n".join(cv)
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
        data[ck] = "\n".join(cv)

    return data, "\n".join(lines[end + 1:])


def parse_parameters(frontmatter, body):
    """从 body 中的 markdown 表格解析参数"""
    params = []
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


def load_main(py_path, mod_name):
    """动态加载 main.py 并返回 execute 函数"""
    if not os.path.isfile(py_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location(mod_name, py_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        execute = getattr(mod, "execute", None)
        if execute is None:
            print(f"技能 {mod_name} main.py 缺少 execute()")
            return None
        return execute
    except Exception as e:
        print(f"技能 {mod_name} 加载失败: {e}")
        return None
