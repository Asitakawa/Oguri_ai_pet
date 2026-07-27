import os
def execute(_pet=None) -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        from datetime import datetime
        boot = datetime.fromtimestamp(psutil.boot_time())
        up = datetime.now() - boot
        return f"CPU:{cpu}% 内存:{mem.percent}%({mem.used//(1024**3)}G/{mem.total//(1024**3)}G) 磁盘:{disk.percent}% 运行:{up.days}天{up.seconds//3600}小时"
    except ImportError:
        return "需安装 psutil"
    except Exception as e:
        return f"获取失败: {e}"
