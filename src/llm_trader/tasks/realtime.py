"""实时行情调度任务。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, List

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.data.pipelines.realtime_quotes import RealtimeQuotesPipeline


LOGGER = logging.getLogger("tasks.realtime")


def fetch_realtime_quotes(symbols: Iterable[str]) -> None:
    pipeline = RealtimeQuotesPipeline()
    records = pipeline.sync(list(symbols))
    LOGGER.info("Realtime fetch complete", extra={"records": len(records), "timestamp": datetime.utcnow().isoformat()})


def start_scheduler(symbols: List[str], interval_minutes: int = 1) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_realtime_quotes, "interval", minutes=interval_minutes, args=[symbols])
    scheduler.start()
    LOGGER.info("Realtime scheduler started", extra={"symbols": symbols, "interval": interval_minutes})
    return scheduler
