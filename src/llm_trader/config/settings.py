"""应用配置加载与缓存模块。

该模块负责从环境变量或 .env 文件中解析项目所需的核心配置，
并提供懒加载的单例访问方法，避免重复解析。所有注释均使用中文。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

# python-dotenv 在尚未安装依赖时可能不可用，因此提供兜底实现
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - 仅在缺失依赖时触发
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        """当 python-dotenv 缺失时提供空实现，避免导入失败。"""

        return False

# 预先加载 .env（如果存在）
load_dotenv()


def _getenv(key: str, default: str) -> str:
    """读取环境变量，若不存在则返回默认值。"""

    value = os.getenv(key, default)
    return value.strip() if isinstance(value, str) else value


def _env_bool(key: str, default: bool) -> bool:
    """将环境变量解析为布尔值。"""

    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    """将环境变量解析为整数，无法转换时返回默认值。"""

    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    """将环境变量解析为浮点数。"""

    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class DataStoreSettings:
    """数据存储相关配置。"""

    base_dir: Path = field(
        default_factory=lambda: Path(_getenv("DATA_STORE_DIR", "data_store"))
    )
    parquet_partition_template: str = field(
        default_factory=lambda: _getenv("DATA_PARQUET_PARTITION_TEMPLATE", "freq/symbol/%Y%m")
    )
    auto_create: bool = field(default_factory=lambda: _env_bool("DATA_AUTO_CREATE", True))

    def resolve_base_dir(self) -> Path:
        """返回绝对路径，必要时创建目录。"""

        path = self.base_dir.expanduser().resolve()
        if self.auto_create:
            path.mkdir(parents=True, exist_ok=True)
        return path


@dataclass
class ApiSettings:
    """服务层与健康检查相关配置。"""

    host: str = field(default_factory=lambda: _getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("API_PORT", 8000))
    reload: bool = field(default_factory=lambda: _env_bool("API_RELOAD", True))
    docs_enabled: bool = field(default_factory=lambda: _env_bool("API_DOCS_ENABLED", True))
    root_path: str = field(default_factory=lambda: _getenv("API_ROOT_PATH", ""))


@dataclass
class SchedulerSettings:
    """调度与任务队列配置。"""

    enabled: bool = field(default_factory=lambda: _env_bool("SCHEDULER_ENABLED", True))
    timezone: str = field(default_factory=lambda: _getenv("SCHEDULER_TIMEZONE", "Asia/Shanghai"))
    max_workers: int = field(default_factory=lambda: _env_int("SCHEDULER_MAX_WORKERS", 4))


@dataclass
class LoggingSettings:
    """日志相关配置。"""

    level: str = field(default_factory=lambda: _getenv("LOG_LEVEL", "INFO"))
    json_enabled: bool = field(default_factory=lambda: _env_bool("LOG_JSON", False))
    log_dir: Optional[Path] = field(
        default_factory=lambda: Path(_getenv("LOG_DIR", "")).expanduser().resolve()
        if _getenv("LOG_DIR", "") else None
    )


@dataclass
class RiskSettings:
    """交易风险控制配置。"""

    max_equity_drawdown: float = field(default_factory=lambda: _env_float("RISK_MAX_EQUITY_DRAWDOWN", 0.1))
    max_position_ratio: float = field(default_factory=lambda: _env_float("RISK_MAX_POSITION_RATIO", 0.3))
    alert_channel: str = field(default_factory=lambda: _getenv("RISK_ALERT_CHANNEL", "log"))


@dataclass
class AppSettings:
    """应用全局配置集合。"""

    environment: str = field(default_factory=lambda: _getenv("APP_ENV", "development"))
    data_store: DataStoreSettings = field(default_factory=DataStoreSettings)
    api: ApiSettings = field(default_factory=ApiSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """返回全局唯一的配置实例。"""

    return AppSettings()


__all__ = [
    "AppSettings",
    "DataStoreSettings",
    "ApiSettings",
    "SchedulerSettings",
    "LoggingSettings",
    "RiskSettings",
    "get_settings",
]
