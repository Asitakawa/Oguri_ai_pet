"""
小栗帽桌宠 - 程序入口（单实例锁）
"""
import os
import sys
import ctypes


def _check_instance(lock_path=".pet.lock"):
    """检测是否有已在运行的同名进程。返回 True 表示可以继续。"""
    try:
        if os.path.exists(lock_path):
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            try:
                import psutil
                if psutil.pid_exists(pid):
                    for proc in psutil.process_iter(['pid', 'name']):
                        if proc.info['pid'] == pid:
                            cmd = proc.cmdline()
                            if any('main.py' in c or 'Oguri' in c for c in cmd):
                                return False, pid
                            break
                else:
                    return True, None
            except ImportError:
                try:
                    os.kill(pid, 0)
                    return False, pid
                except (OSError, ProcessLookupError):
                    return True, None
        return True, None
    except Exception:
        return True, None


def _write_lock(lock_path=".pet.lock"):
    with open(lock_path, 'w') as f:
        f.write(str(os.getpid()))


def _remove_lock(lock_path=".pet.lock"):
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except Exception:
        pass


if __name__ == "__main__":
    LOCK = ".pet.lock"
    ok, existing_pid = _check_instance(LOCK)
    if not ok:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"小栗帽已经在运行中啦～\n\n（进程 ID: {existing_pid}）\n同一路径下只能启动一个小栗帽哦🍙",
            "小栗帽桌宠",
            0x40
        )
        sys.exit(0)

    _write_lock(LOCK)

    try:
        from src.utils import get_resource_path
        from src.pet_core import KurumiPet

        os.makedirs(get_resource_path("pic"), exist_ok=True)
        KurumiPet()
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
    except Exception as e:
        print(f"启动失败：{e}")
        import traceback
        traceback.print_exc()
        input("按回车退出...")
    finally:
        _remove_lock(LOCK)
