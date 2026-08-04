"""
小栗帽桌宠 - 程序入口（单实例锁 + 重启支持）
"""
import atexit
import ctypes
import os
import socket
import sys
import time

from core.paths import get_data_path
from utils.logger import get_logger

log = get_logger("main")

_LOCK_PORT = 45897
_LOCK_FILE = ".pet.lock"  # 位于 data/ 下
_RESTART_WAIT_SECONDS = 8.0
_LOCK_SOCKET = None


def _write_lock_file() -> bool:
    """写入 PID 锁文件，作为端口锁的补充。"""
    try:
        with open(get_data_path(_LOCK_FILE), "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return True
    except OSError as e:
        log.warning("写入锁文件失败: %s", e)
        return False


def _remove_lock_file() -> None:
    try:
        path = get_data_path(_LOCK_FILE)
        if os.path.exists(path):
            os.remove(path)
    except OSError as e:
        log.warning("删除锁文件失败: %s", e)


def _check_instance(wait_seconds: float = 0.0) -> bool:
    """独占端口 _LOCK_PORT；wait_seconds>0 时在窗口期内重试（用于 --restart）。"""
    global _LOCK_SOCKET
    deadline = time.time() + wait_seconds
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", _LOCK_PORT))
            sock.listen(1)
            _LOCK_SOCKET = sock
            return True
        except socket.error:
            if time.time() >= deadline:
                return False
            time.sleep(0.3)


def _notify_already_running() -> None:
    try:
        ctypes.windll.user32.MessageBoxW(
            0, "小栗帽已经在运行中啦～\n\n同一路径下只能启动一个小栗帽哦🍙",
            "小栗帽桌宠", 0x40,
        )
    except Exception as e:
        log.warning("无法弹出重复运行提示: %s", e)


def main() -> None:
    restart = "--restart" in sys.argv
    if not _check_instance(wait_seconds=_RESTART_WAIT_SECONDS if restart else 0.0):
        _notify_already_running()
        sys.exit(0)

    _write_lock_file()
    atexit.register(_remove_lock_file)

    # 源码模式下确保图片目录存在；frozen 模式资源随包内置在 _MEIPASS，无需创建
    if not getattr(sys, "_MEIPASS", None):
        os.makedirs("resources/images", exist_ok=True)

    try:
        from ui.pet_window import KurumiPet
        KurumiPet()
    except KeyboardInterrupt:
        log.info("程序已被用户中断")
    except Exception:
        log.exception("启动失败")
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "小栗帽启动失败，请查看日志文件 data/logs/kurumi.log",
                "小栗帽桌宠", 0x10,
            )
        except Exception:
            pass


if __name__ == "__main__":
    main()
