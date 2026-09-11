"""统一日志入口 — 控制台 + 数据目录 logs/ 下的轮转文件"""
from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from core.paths import get_log_dir

_ROOT_NAME = "kurumi"
_LOG_LEVEL = logging.INFO
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_MAX_BYTES = 1024 * 1024
_BACKUP_COUNT = 3
_CONSOLE = True

# 日志里出现的管理面板 token 必须打码：拿到它就能通过本地 REST 控制桌宠进程
# （重启/退出/执行技能/截屏），而日志文件可能被备份或同步工具读走。
_TOKEN_PATTERNS = (
    # http://127.0.0.1:1234/?token=XXXX
    (re.compile(r"(token=)[A-Za-z0-9_\-]+"), r"\1***"),
    # API Key（.env 里是 base64，这里防的是明文误入日志）
    (re.compile(r"(sk-)[A-Za-z0-9_\-]{8,}"), r"\1***"),
    (re.compile(r"(API_KEY\s*[=:]\s*)\S+"), r"\1***"),
)


class _ScrubFilter(logging.Filter):
    """在写入任何 handler 之前把敏感片段替换掉。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = _scrub(record.getMessage())
            record.args = ()
        except Exception:
            pass
        return True


def _scrub(text: str) -> str:
    for pattern, repl in _TOKEN_PATTERNS:
        text = pattern.sub(repl, text)
    return text


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
        fh = RotatingFileHandler(
            os.path.join(get_log_dir(), "kurumi.log"),
            maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e:
        root.warning("初始化日志文件失败: %s", e)
    root.addFilter(_ScrubFilter())


def get_logger(name: str = "kurumi") -> logging.Logger:
    """返回项目统一 logger（自动挂载控制台 + 轮转文件处理器）。"""
    _setup_root()
    if not name or name == _ROOT_NAME:
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
