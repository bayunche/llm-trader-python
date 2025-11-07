"""受控交易调度任务。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Mapping, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.config import get_settings
from llm_trader.common import create_redis_client
from llm_trader.common.logging import get_logger
from llm_trader.data.ingestion import DataIngestionService
from llm_trader.db.session import create_session_factory
from llm_trader.observation import ObservationBuilder
from llm_trader.pipeline.auto import record_trading_run_summary
from llm_trader.trading import RiskPolicy, RiskThresholds
from llm_trader.trading.manager import run_managed_trading_cycle
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.decision import ActorService, CheckerService, DecisionService
from llm_trader.model_gateway import ModelGateway


LOGGER = get_logger("tasks.managed_cycle")

_SESSION_FACTORY = None
_DATA_SERVICE: Optional[DataIngestionService] = None
_OBSERVATION_BUILDER: Optional[ObservationBuilder] = None
_LAST_MASTER_SYNC: Optional[date] = None
_MODEL_GATEWAY: Optional[ModelGateway] = None
_ACTOR_SERVICE: Optional[ActorService] = None
_CHECKER_SERVICE: Optional[CheckerService] = None
_DECISION_SERVICE: Optional[DecisionService] = None


def _ensure_services(symbol_universe_limit: int) -> Tuple[DataIngestionService, ObservationBuilder]:
    """延迟初始化数据采集与观测构建服务。"""

    global _SESSION_FACTORY, _DATA_SERVICE, _OBSERVATION_BUILDER
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = create_session_factory()
    if _DATA_SERVICE is None:
        _DATA_SERVICE = DataIngestionService(
            session_factory=_SESSION_FACTORY,
            symbol_universe_limit=symbol_universe_limit,
        )
    if _OBSERVATION_BUILDER is None:
        redis_client = create_redis_client()
        ttl_ms = get_settings().trading.observation_ttl_ms
        _OBSERVATION_BUILDER = ObservationBuilder(
            session_factory=_SESSION_FACTORY,
            redis_client=redis_client,
            valid_ttl_ms=ttl_ms,
            symbol_universe_limit=symbol_universe_limit,
        )
    return _DATA_SERVICE, _OBSERVATION_BUILDER


def _ensure_decision_services(session_factory):
    """初始化决策服务与模型网关，若未启用则返回空值。"""

    settings = get_settings().model_gateway
    if not settings.enabled or not settings.endpoints:
        return None, None, None

    global _MODEL_GATEWAY, _ACTOR_SERVICE, _CHECKER_SERVICE, _DECISION_SERVICE
    if _MODEL_GATEWAY is None:
        _MODEL_GATEWAY = ModelGateway(session_factory=session_factory)
    if _ACTOR_SERVICE is None:
        _ACTOR_SERVICE = ActorService(_MODEL_GATEWAY)
    if _CHECKER_SERVICE is None:
        _CHECKER_SERVICE = CheckerService(_MODEL_GATEWAY)
    if _DECISION_SERVICE is None:
        _DECISION_SERVICE = DecisionService(session_factory=session_factory)
    return _ACTOR_SERVICE, _CHECKER_SERVICE, _DECISION_SERVICE


def _sync_daily_master_symbols(service: DataIngestionService) -> None:
    """每天只同步一次主表，避免频繁请求。"""

    global _LAST_MASTER_SYNC
    today = datetime.utcnow().date()
    if _LAST_MASTER_SYNC == today:
        return
    service.sync_master_symbols()
    _LAST_MASTER_SYNC = today


def run_cycle(
    config: TradingCycleConfig | Mapping[str, object],
    *,
    policy: RiskPolicy | None = None,
    **runtime_kwargs,
) -> None:
    trading_config = _ensure_trading_config(config)
    settings = get_settings().trading
    symbol_limit = trading_config.symbol_universe_limit or settings.symbol_universe_limit
    data_service_override = runtime_kwargs.pop("data_service", None)
    observation_builder_override = runtime_kwargs.pop("observation_builder", None)
    if data_service_override is not None and observation_builder_override is not None:
        data_service = data_service_override
        observation_builder = observation_builder_override
    else:
        data_service, observation_builder = _ensure_services(symbol_limit)
    _sync_daily_master_symbols(data_service)
    try:
        data_service.sync_account_snapshot()
        quotes = data_service.sync_realtime_quotes(trading_config.symbols or None)
        observation_payload = observation_builder.build()
        LOGGER.info(
            "最新观测已生成",
            extra={
                "observation_id": observation_payload.observation_id,
                "symbols": len(observation_payload.universe),
                "cache_metrics": observation_builder.cache_metrics,
            },
        )
    except Exception as exc:  # pragma: no cover - 数据采集失败会阻断后续执行
        LOGGER.exception("采集数据或构建观测失败", extra={"error": str(exc)})
        raise

    actor_service = checker_service = decision_service = None
    try:
        actor_service, checker_service, decision_service = _ensure_decision_services(_SESSION_FACTORY)
    except Exception as exc:  # pragma: no cover - 决策栈初始化失败不阻断主流程
        LOGGER.warning(
            "初始化决策服务失败，继续执行但不记录决策结果",
            extra={"error": str(exc)},
        )

    result = run_managed_trading_cycle(
        trading_config,
        policy=policy,
        quotes=quotes,
        observation_id=observation_payload.observation_id,
        observation=observation_payload,
        actor_service=actor_service,
        checker_service=checker_service,
        decision_service=decision_service,
        **runtime_kwargs,
    )
    message = (
        "Managed cycle finished | strategy=%s session=%s orders=%s trades=%s proceed=%s alerts=%s"
        % (
            trading_config.strategy_id,
            trading_config.session_id,
            result.raw_result["orders_executed"],
            result.raw_result["trades_filled"],
            result.decision.proceed,
            ",".join(result.decision.alerts) if result.decision.alerts else "-",
        )
    )
    status = "executed" if result.decision.proceed else "risk_blocked"
    try:
        derived_config = result.raw_result.get("config")
        target_config = derived_config if isinstance(derived_config, TradingCycleConfig) else trading_config
        record_trading_run_summary(target_config, result, status)
    except Exception as exc:  # pragma: no cover - 写入失败时仅记录日志
        LOGGER.warning(
            "记录调度交易摘要失败",
            extra={"error": str(exc)},
        )
    if result.decision.proceed:
        LOGGER.info(message)
    else:
        LOGGER.warning(message)


def start_managed_scheduler(
    configs: Iterable[TradingCycleConfig | Mapping[str, object]],
    *,
    interval_minutes: int | None = None,
    policy: RiskPolicy | None = None,
) -> BackgroundScheduler:
    settings = get_settings().trading
    interval = interval_minutes if interval_minutes is not None else settings.scheduler_interval_minutes
    scheduler = BackgroundScheduler()
    normalized_configs = [_ensure_trading_config(config) for config in configs]
    for config in normalized_configs:
        scheduler.add_job(
            run_cycle,
            "interval",
            minutes=interval,
            args=[config],
            kwargs={"policy": policy},
        )
    scheduler.start()
    LOGGER.info(
        "Managed scheduler started | strategies=%s",
        ",".join(sorted({cfg.strategy_id for cfg in normalized_configs})),
    )
    return scheduler


def _ensure_trading_config(config: TradingCycleConfig | Mapping[str, object]) -> TradingCycleConfig:
    if isinstance(config, TradingCycleConfig):
        return config
    params = dict(config)
    lookback_raw = params.pop("lookback_days", None)
    lookback_days: Optional[int] = None
    if isinstance(lookback_raw, (int, float)) and lookback_raw > 0:
        lookback_days = int(lookback_raw)
    elif isinstance(lookback_raw, str):
        try:
            lookback_days = int(lookback_raw)
        except ValueError:
            lookback_days = None
    if lookback_days and not params.get("history_start"):
        now = datetime.utcnow()
        params.setdefault("history_end", now)
        params["history_start"] = now - timedelta(days=lookback_days)
    symbols = params.get("symbols")
    if isinstance(symbols, str):
        params["symbols"] = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    indicators = params.get("indicators")
    if isinstance(indicators, str):
        params["indicators"] = [item.strip() for item in indicators.split(",") if item.strip()]
    for key in ("history_start", "history_end"):
        value = params.get(key)
        if isinstance(value, str) and value:
            params[key] = datetime.fromisoformat(value)
    return TradingCycleConfig(**params)  # type: ignore[arg-type]


def sync_account_snapshot(symbol_universe_limit: int | None = None) -> None:
    """独立触发一次账户快照采集，用于调度任务。"""

    settings = get_settings().trading
    limit = symbol_universe_limit or settings.symbol_universe_limit
    service, _ = _ensure_services(limit)
    service.sync_account_snapshot()


__all__ = ["run_cycle", "start_managed_scheduler", "sync_account_snapshot"]
