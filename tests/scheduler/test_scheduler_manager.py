from __future__ import annotations

import json
from pathlib import Path

from llm_trader.scheduler import build_scheduler_config, export_scheduler_config
from llm_trader.config.settings import AppSettings, SchedulerSettings, TradingSettings


def _make_settings() -> AppSettings:
    trading = TradingSettings(
        session_id="session-demo",
        strategy_id="strategy-demo",
        symbols=["600000.SH", "000001.SZ"],
        objective="自动交易",
        indicators=["sma"],
        freq="D",
        lookback_days=10,
        llm_model="gpt-4.1-mini",
        llm_base_url="http://localhost:8080/v1",
        initial_cash=2_000_000.0,
        only_latest_bar=False,
        symbol_universe_limit=100,
        scheduler_interval_minutes=15,
        selection_metric="amount",
    )
    scheduler = SchedulerSettings(timezone="Asia/Shanghai", enabled=True)
    return AppSettings(trading=trading, scheduler=scheduler)


def test_build_scheduler_config_produces_three_jobs() -> None:
    settings = _make_settings()
    payload = build_scheduler_config(settings)

    assert payload["timezone"] == "Asia/Shanghai"
    jobs = payload["jobs"]
    assert {job["id"] for job in jobs} == {"realtime-quotes", "account-snapshot", "managed-trading"}

    trading_job = next(job for job in jobs if job["id"] == "managed-trading")
    config = trading_job["kwargs"]["config"]
    assert config["lookback_days"] == 10
    assert config["symbols"] == ["600000.SH", "000001.SZ"]
    assert config["indicators"] == ["sma"]

    account_job = next(job for job in jobs if job["id"] == "account-snapshot")
    assert account_job["kwargs"]["symbol_universe_limit"] == 100


def test_export_scheduler_config_writes_file(tmp_path: Path) -> None:
    settings = _make_settings()
    target = tmp_path / "scheduler.json"
    payload = export_scheduler_config(target, settings=settings)

    assert target.exists()
    with target.open("r", encoding="utf-8") as fp:
        loaded = json.load(fp)
    assert loaded == payload
