"""应用配置加载与缓存模块。

该模块负责从环境变量或 .env 文件中解析项目所需的核心配置，
并提供懒加载的单例访问方法，避免重复解析。所有注释均使用中文。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from llm_trader.model_gateway.config import ModelEndpointSettings, ModelGatewaySettings

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


def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_json(key: str) -> Any:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


_VALID_EXECUTION_MODES = {"sandbox", "live"}


def _env_execution_mode(key: str, default: str = "sandbox") -> str:
    """解析交易执行模式，只允许 sandbox/live，两者之外回退为默认值。"""

    raw = _getenv(key, default).lower()
    if raw in _VALID_EXECUTION_MODES:
        return raw
    return default.lower()


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
    max_equity_volatility: float = field(default_factory=lambda: _env_float("RISK_MAX_EQUITY_VOLATILITY", 0.0))
    max_sector_exposure: float = field(default_factory=lambda: _env_float("RISK_MAX_SECTOR_EXPOSURE", 0.0))
    max_holding_days: int = field(default_factory=lambda: _env_int("RISK_MAX_HOLDING_DAYS", 0))


@dataclass
class TradingSettings:
    """交易相关默认配置。"""

    session_id: str = field(default_factory=lambda: _getenv("TRADING_SESSION", "session-demo"))
    strategy_id: str = field(default_factory=lambda: _getenv("TRADING_STRATEGY", "strategy-demo"))
    symbols: List[str] = field(default_factory=lambda: _env_list("TRADING_SYMBOLS", []))
    objective: str = field(default_factory=lambda: _getenv("TRADING_OBJECTIVE", "自动交易"))
    freq: str = field(default_factory=lambda: _getenv("TRADING_FREQ", "D"))
    indicators: List[str] = field(default_factory=lambda: _env_list("TRADING_INDICATORS", ["sma", "ema"]))
    initial_cash: float = field(default_factory=lambda: _env_float("TRADING_INITIAL_CASH", 1_000_000.0))
    lookback_days: int = field(default_factory=lambda: _env_int("TRADING_LOOKBACK_DAYS", 120))
    llm_model: str = field(default_factory=lambda: _getenv("TRADING_LLM_MODEL", "gpt-4.1-mini"))
    only_latest_bar: bool = field(default_factory=lambda: _env_bool("TRADING_ONLY_LATEST", True))
    scheduler_interval_minutes: int = field(default_factory=lambda: _env_int("TRADING_SCHEDULER_INTERVAL", 60))
    run_backtest: bool = field(default_factory=lambda: _env_bool("TRADING_RUN_BACKTEST", True))
    backtest_min_return: float = field(
        default_factory=lambda: _env_float("TRADING_BACKTEST_MIN_RETURN", 0.0)
    )
    backtest_max_drawdown: float = field(
        default_factory=lambda: _env_float("TRADING_BACKTEST_MAX_DRAWDOWN", 0.2)
    )
    llm_base_url: str = field(default_factory=lambda: _getenv("TRADING_LLM_BASE_URL", ""))
    symbol_universe_limit: int = field(default_factory=lambda: _env_int("TRADING_SYMBOL_UNIVERSE_LIMIT", 200))
    selection_metric: str = field(default_factory=lambda: _getenv("TRADING_SELECTION_METRIC", "amount"))
    execution_mode: str = field(
        default_factory=lambda: _env_execution_mode("TRADING_EXECUTION_MODE", "sandbox")
    )
    broker_provider: str = field(default_factory=lambda: _getenv("TRADING_BROKER_PROVIDER", "mock"))
    broker_account: str = field(default_factory=lambda: _getenv("TRADING_BROKER_ACCOUNT", "demo-account"))
    broker_base_url: str = field(default_factory=lambda: _getenv("TRADING_BROKER_BASE_URL", ""))
    broker_api_key: str = field(default_factory=lambda: _getenv("TRADING_BROKER_API_KEY", ""))
    report_output_dir: str = field(default_factory=lambda: _getenv("REPORT_OUTPUT_DIR", "reports"))
    observation_ttl_ms: int = field(default_factory=lambda: _env_int("TRADING_OBSERVATION_TTL_MS", 3000))


@dataclass
class MonitoringSettings:
    """监控与告警配置。"""

    channel: str = field(default_factory=lambda: _getenv("MONITORING_ALERT_CHANNEL", "log"))


@dataclass
class DatabaseSettings:
    """数据库连接配置。"""

    url: str = field(default_factory=lambda: _getenv("DATABASE_URL", "sqlite:///llm_trader.db"))
    echo: bool = field(default_factory=lambda: _env_bool("DATABASE_ECHO", False))


@dataclass
class RedisSettings:
    """Redis 缓存配置。"""

    enabled: bool = field(default_factory=lambda: _env_bool("REDIS_ENABLED", False))
    url: str = field(default_factory=lambda: _getenv("REDIS_URL", "redis://localhost:6379/0"))
    decode_responses: bool = field(default_factory=lambda: _env_bool("REDIS_DECODE_RESPONSES", False))


def _load_model_endpoints(default_model: str) -> List[ModelEndpointSettings]:
    raw = _env_json("MODEL_GATEWAY_ENDPOINTS")
    endpoints: List[ModelEndpointSettings] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                endpoints.append(
                    ModelEndpointSettings(
                        name=str(item.get("name") or f"endpoint-{len(endpoints)+1}"),
                        base_url=str(item["base_url"]),
                        api_key=item.get("api_key") or None,
                        weight=float(item.get("weight", 1.0) or 1.0),
                        timeout=float(item.get("timeout", 30.0) or 30.0),
                        max_retries=int(item.get("max_retries", 2) or 2),
                        enabled=bool(item.get("enabled", True)),
                        prompt_cost_per_1k=float(item.get("prompt_cost_per_1k", 0.0) or 0.0),
                        completion_cost_per_1k=float(item.get("completion_cost_per_1k", 0.0) or 0.0),
                        default_params=item.get("default_params") or {},
                        headers=item.get("headers") or {},
                        circuit_breaker=item.get("circuit_breaker") or {},
                        metadata=item.get("metadata") or {},
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"MODEL_GATEWAY_ENDPOINTS 配置无效: {exc}") from exc
    if endpoints:
        return endpoints

    fallback_url = _getenv("MODEL_GATEWAY_FALLBACK_BASE_URL", "") or _getenv("TRADING_LLM_BASE_URL", "")
    if fallback_url:
        endpoints.append(
            ModelEndpointSettings(
                name="default",
                base_url=fallback_url,
                api_key=_getenv("MODEL_GATEWAY_API_KEY", os.getenv("OPENAI_API_KEY", "")) or None,
                weight=1.0,
                timeout=float(_getenv("MODEL_GATEWAY_TIMEOUT", "30")),
                max_retries=int(_getenv("MODEL_GATEWAY_MAX_RETRIES", "2")),
                default_params={},
                headers={},
                circuit_breaker={},
            )
        )
    return endpoints


def _load_model_gateway_settings() -> ModelGatewaySettings:
    default_model = _getenv("MODEL_GATEWAY_DEFAULT_MODEL", _getenv("TRADING_LLM_MODEL", "gpt-4.1-mini"))
    endpoints = _load_model_endpoints(default_model)
    return ModelGatewaySettings(
        enabled=_env_bool("MODEL_GATEWAY_ENABLED", True),
        default_model=default_model,
        audit_enabled=_env_bool("MODEL_GATEWAY_AUDIT_ENABLED", True),
        endpoints=endpoints,
    )


@dataclass
class AppSettings:
    """应用全局配置集合。"""

    environment: str = field(default_factory=lambda: _getenv("APP_ENV", "development"))
    data_store: DataStoreSettings = field(default_factory=DataStoreSettings)
    api: ApiSettings = field(default_factory=ApiSettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    risk: RiskSettings = field(default_factory=RiskSettings)
    trading: TradingSettings = field(default_factory=TradingSettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    model_gateway: ModelGatewaySettings = field(default_factory=_load_model_gateway_settings)


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
    "MonitoringSettings",
    "RiskSettings",
    "TradingSettings",
    "DatabaseSettings",
    "RedisSettings",
    "ModelGatewaySettings",
    "ModelEndpointSettings",
    "get_settings",
]
