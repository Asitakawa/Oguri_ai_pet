"""资源/数据路径解析

两类路径要分清：

- **资源**（`resources/`、`skills/`、`web/dist`）：随包分发，只读。
  PyInstaller 解包到 `sys._MEIPASS`，源码模式就是仓库根。
- **数据**（聊天记录、设置、技能配置、日志）：用户可写，必须落在确实能写的地方。

数据目录的选址顺序：
1. `OGURI_DATA_DIR` 环境变量（便于测试与多实例隔离）
2. EXE / 仓库同级目录下的 `data/`（便携模式，历史行为）
3. `%APPDATA%/OguriPet`（安装到 Program Files 等只读位置时的回退）

选址结果会缓存，避免每次调用都做写测试。
"""
from __future__ import annotations

import os
import sys

_DATA_DIR: str | None = None

_ENV_OVERRIDE = "OGURI_DATA_DIR"


def get_app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


def _is_writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(probe)
        return True
    except OSError:
        return False


def _roaming_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "OguriPet")


def resolve_data_dir() -> str:
    """确定并缓存数据目录。"""
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR

    override = os.environ.get(_ENV_OVERRIDE)
    if override:
        os.makedirs(override, exist_ok=True)
        _DATA_DIR = override
        return _DATA_DIR

    portable = os.path.join(get_app_dir(), "data")
    # 已存在就认它（兼容老用户），否则做一次写测试
    if os.path.isdir(portable) or _is_writable(portable):
        _DATA_DIR = portable
        return _DATA_DIR

    fallback = _roaming_dir()
    os.makedirs(fallback, exist_ok=True)
    _DATA_DIR = fallback
    return _DATA_DIR


def get_data_path(filename: str) -> str:
    data_dir = resolve_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)


def get_log_dir() -> str:
    log_dir = os.path.join(resolve_data_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def reset_cache() -> None:
    """测试用：清掉缓存的目录选择。"""
    global _DATA_DIR
    _DATA_DIR = None
