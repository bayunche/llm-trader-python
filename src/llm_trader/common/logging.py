"""统一的日志配置模块。

该模块提供日志配置的构建与初始化函数，默认使用标准库 logging，
并根据配置决定是否输出到文件或以 JSON 格式记录。"""

from __future__ import annotations

import json
import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Any, Dict, Optional

from llm_trader.config import LoggingSettings, get_settings


def _default_formatter(json_enabled: bool) -> Dict[str, Any]:
    """根据配置返回格式化器设置。"""

    if json_enabled:
        return {
            "class": "llm_trader.common.logging.JsonFormatter",
            "fmt": "%(message)s",
        }
    return {
        "class": "logging.Formatter",
        "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }


def _default_handlers(level: str, log_dir: Optional[Path], json_enabled: bool) -> Dict[str, Any]:
    """构造控制台与文件处理器配置。"""

    handlers: Dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": level,
            "formatter": "default",
        }
    }

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "default",
            "filename": str(log_dir / "app.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }

    return handlers


def build_logging_config(settings: Optional[LoggingSettings] = None) -> Dict[str, Any]:
    """根据配置对象生成 dictConfig 需要的字典。"""

    settings = settings or get_settings().logging
    formatter_settings = _default_formatter(settings.json_enabled)
    handlers = _default_handlers(settings.level, settings.log_dir, settings.json_enabled)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": formatter_settings,
        },
        "handlers": handlers,
        "loggers": {
            "": {
                "handlers": list(handlers.keys()),
                "level": settings.level,
            }
        },
    }


def setup_logging(force: bool = False) -> None:
    """初始化日志系统，避免重复配置。"""

    root_logger = logging.getLogger()
    if root_logger.handlers and not force:
        return

    dictConfig(build_logging_config())


def get_logger(name: str) -> logging.Logger:
    """获取命名日志记录器，必要时自动初始化。"""

    if not logging.getLogger().handlers:
        setup_logging()
    return logging.getLogger(name)


class JsonFormatter(logging.Formatter):
    """简单的 JSON 日志格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


__all__ = ["setup_logging", "get_logger", "build_logging_config", "JsonFormatter"]
