"""统一日志入口 — 控制台 + data/logs/ 轮转文件"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from core.paths import get_data_path

_ROOT_NAME = "kurumi"
_LOG_LEVEL = logging.INFO
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_MAX_BYTES = 1024 * 1024
_BACKUP_COUNT = 3
_CONSOLE = True


def _setup_root() -> None:
    root = logging.getLogger(_ROOT_NAME)
    if root.handlers:
        return
    root.setLevel(_LOG_LEVEL)
    fmt = logging.Formatter(_FORMAT)
    if _CONSOLE:
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)
    try:
        log_dir = os.path.join(os.path.dirname(get_data_path("x.log")), "logs")
        os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(log_dir, "kurumi.log"),
            maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e:
        root.warning("初始化日志文件失败: %s", e)


def get_logger(name: str = "kurumi") -> logging.Logger:
    """返回项目统一 logger（自动挂载控制台 + 轮转文件处理器）。"""
    _setup_root()
    if not name or name == _ROOT_NAME:
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
