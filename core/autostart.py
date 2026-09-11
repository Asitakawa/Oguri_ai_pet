"""开机自启 — 管理 Windows 启动目录里的快捷方式

用启动文件夹（`shell:startup`）而不是写注册表 Run 键：
- 不需要管理员权限
- 用户随时能在「任务管理器 → 启动」里自己关掉，看得见、可撤销
- 卸载时留个残快捷方式，无害且容易发现
"""
from __future__ import annotations

import os
import subprocess
import sys

from core.paths import get_app_dir
from utils.logger import get_logger

log = get_logger("autostart")

SHORTCUT_NAME = "小栗帽桌宠.lnk"


def _startup_dir() -> str:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise OSError("找不到 APPDATA，无法定位启动目录")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup")


def shortcut_path() -> str:
    return os.path.join(_startup_dir(), SHORTCUT_NAME)


def is_enabled() -> bool:
    try:
        return os.path.isfile(shortcut_path())
    except OSError:
        return False


def _target_and_args() -> tuple:
    """返回 (可执行文件, 参数)。打包后直接指向 EXE，源码模式指向 pythonw。"""
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    # 源码模式：用 pythonw 避免弹控制台窗口
    exe_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(exe_dir, "pythonw.exe")
    if not os.path.isfile(pythonw):
        pythonw = sys.executable
    main_py = os.path.join(get_app_dir(), "main.py")
    return pythonw, f'"{main_py}"'


def enable() -> tuple:
    """创建开机自启快捷方式。返回 (是否成功, 说明)。"""
    if os.name != "nt":
        return False, "仅支持 Windows"
    target, args = _target_and_args()
    if not os.path.isfile(target):
        return False, f"找不到可执行文件: {target}"
    path = shortcut_path()
    workdir = get_app_dir()
    # 用 WScript.Shell 建 .lnk，避免引入 pywin32 依赖
    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$sc = $ws.CreateShortcut('{path}'); "
        f"$sc.TargetPath = '{target}'; "
        f"$sc.Arguments = '{args}'; "
        f"$sc.WorkingDirectory = '{workdir}'; "
        f"$sc.Description = '小栗帽桌宠'; "
        "$sc.Save()"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, timeout=20,
        )
    except Exception as e:
        log.warning("创建快捷方式失败: %s", e)
        return False, f"创建失败: {e}"
    if result.returncode != 0 or not os.path.isfile(path):
        detail = (result.stderr or b"").decode("utf-8", "replace").strip()
        log.warning("创建快捷方式返回码 %s: %s", result.returncode, detail)
        return False, "创建快捷方式失败"
    log.info("已开启开机自启: %s", path)
    return True, "已开启开机自启"


def disable() -> tuple:
    """删除快捷方式。"""
    if os.name != "nt":
        return False, "仅支持 Windows"
    path = shortcut_path()
    if not os.path.isfile(path):
        return True, "开机自启本来就是关闭的"
    try:
        os.remove(path)
    except OSError as e:
        log.warning("删除快捷方式失败: %s", e)
        return False, f"删除失败: {e}"
    log.info("已关闭开机自启")
    return True, "已关闭开机自启"


def set_enabled(value: bool) -> tuple:
    return enable() if value else disable()
