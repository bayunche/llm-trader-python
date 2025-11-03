"""受控交易调度任务。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.config import get_settings
from llm_trader.trading import RiskPolicy, RiskThresholds
from llm_trader.trading.manager import run_managed_trading_cycle
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.common.logging import get_logger


LOGGER = get_logger("tasks.managed_cycle")


def run_cycle(
    config: TradingCycleConfig | Mapping[str, object],
    *,
    policy: RiskPolicy | None = None,
    **runtime_kwargs,
) -> None:
    trading_config = _ensure_trading_config(config)
    result = run_managed_trading_cycle(trading_config, policy=policy, **runtime_kwargs)
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


__all__ = ["run_cycle", "start_managed_scheduler"]
