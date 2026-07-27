"""
小栗帽桌宠 - 程序入口（单实例锁）
"""
import os
import sys
import socket
import ctypes

_LOCK_PORT = 45897
_LOCK_SOCKET = None


def _check_instance() -> bool:
    global _LOCK_SOCKET
    try:
        _LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _LOCK_SOCKET.bind(("127.0.0.1", _LOCK_PORT))
        _LOCK_SOCKET.listen(1)
        return True
    except socket.error:
        return False


if __name__ == "__main__":
    if not _check_instance():
        ctypes.windll.user32.MessageBoxW(
            0, "小栗帽已经在运行中啦～\n\n同一路径下只能启动一个小栗帽哦\U0001F359",
            "小栗帽桌宠", 0x40,
        )
        sys.exit(0)

    try:
        from ui.pet_window import KurumiPet
        os.makedirs("resources/images", exist_ok=True)
        KurumiPet()
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
    except Exception as e:
        print(f"启动失败：{e}")
        import traceback
        traceback.print_exc()
        input("按回车退出...")
