"""受控交易调度任务。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.trading import RiskPolicy, RiskThresholds
from llm_trader.trading.manager import run_managed_trading_cycle
from llm_trader.trading.orchestrator import TradingCycleConfig


LOGGER = logging.getLogger("tasks.managed_cycle")


def run_cycle(config: TradingCycleConfig, *, policy: RiskPolicy | None = None) -> None:
    result = run_managed_trading_cycle(config, policy=policy)
    level = logging.INFO if result.decision.proceed else logging.WARNING
    LOGGER.log(
        level,
        "Managed cycle finished",
        extra={
            "strategy": config.strategy_id,
            "session": config.session_id,
            "orders_executed": result.raw_result["orders_executed"],
            "trades_filled": result.raw_result["trades_filled"],
            "alerts": result.decision.alerts,
        },
    )


def start_managed_scheduler(
    configs: Iterable[TradingCycleConfig],
    *,
    interval_minutes: int = 30,
    policy: RiskPolicy | None = None,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    for config in configs:
        scheduler.add_job(run_cycle, "interval", minutes=interval_minutes, args=[config], kwargs={"policy": policy})
    scheduler.start()
    LOGGER.info("Managed scheduler started", extra={"strategies": [c.strategy_id for c in configs]})
    return scheduler


__all__ = ["run_cycle", "start_managed_scheduler"]
