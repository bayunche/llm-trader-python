"""AI 自动交易编排单元测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence

import pandas as pd
import pytest
import json

from llm_trader.backtest.models import Order, OrderSide
from llm_trader.data import DatasetKind, default_manager
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.strategy.llm_generator import LLMStrategySuggestion
from llm_trader.strategy.logger import LLMStrategyLogRepository
from llm_trader.strategy.engine import RuleConfig
from llm_trader.trading import (
    TradingCycleConfig,
    TradingSession,
    TradingSessionConfig,
    run_ai_trading_cycle,
)


class FakeGenerator:
    def __init__(self, rules: Sequence[RuleConfig]) -> None:
        self._suggestion = LLMStrategySuggestion(
            description="demo",
            rules=list(rules),
            selected_symbols=["600000.SH"],
        )
        self.last_prompt = None
        self.last_raw_response = None

    def generate(self, _context) -> LLMStrategySuggestion:
        self.last_prompt = "fake prompt"
        self.last_raw_response = json.dumps({"description": "demo", "rules": []})
        return self._suggestion


class FakeRealtimePipeline:
    def __init__(self, quotes: List[Dict[str, object]]) -> None:
        self._quotes = quotes

    def sync(self, symbols: Sequence[str]) -> List[Dict[str, object]]:
        return [quote for quote in self._quotes if quote["symbol"] in symbols]


def _load_bars(_: Sequence[str], __: str, ___, ____):
    raise AssertionError("Should be patched in test")


def test_run_ai_trading_cycle_executes_orders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base_dir = tmp_path / "data_store"
    manager = default_manager(base_dir=base_dir)
    repo = ParquetRepository(manager=manager)

    history = [
        {
            "symbol": "600000.SH",
            "dt": datetime(2024, 1, 1, 9, 30),
            "freq": "D",
            "open": 9.5,
            "high": 10.2,
            "low": 9.4,
            "close": 10.1,
            "volume": 100000,
            "amount": 1000000,
        },
        {
            "symbol": "600000.SH",
            "dt": datetime(2024, 1, 2, 9, 30),
            "freq": "D",
            "open": 10.0,
            "high": 10.4,
            "low": 9.8,
            "close": 10.3,
            "volume": 120000,
            "amount": 1230000,
        },
    ]

    def fake_load(symbols, freq, start, end):
        assert symbols == ["600000.SH"]
        return history

    generator = FakeGenerator(
        [
            RuleConfig(
                indicator="sma",
                column="close",
                params={"window": 1},
                operator=">",
                threshold=9.0,
            )
        ]
    )
    realtime = FakeRealtimePipeline(
        [
            {
                "symbol": "600000.SH",
                "last_price": 10.5,
                "change_ratio": 1.2,
                "turnover_rate": 3.5,
            }
        ]
    )

    session = TradingSession(
        TradingSessionConfig(session_id="session-1", strategy_id="strategy-ai", initial_cash=100000.0),
        repository=repo,
    )
    log_repo = LLMStrategyLogRepository(manager=manager)

    result = run_ai_trading_cycle(
        TradingCycleConfig(
            session_id="session-1",
            strategy_id="strategy-ai",
            symbols=["600000.SH"],
            objective="获取日内收益",
            indicators=("sma",),
            history_start=datetime(2024, 1, 1),
        ),
        generator=generator,
        trading_session=session,
        realtime_pipeline=realtime,
        load_ohlcv_fn=fake_load,
        log_repository=log_repo,
    )

    assert result["orders_executed"] >= 1
    assert result["trades_filled"] >= 1
    assert result["selected_symbols"] == ["600000.SH"]

    orders_path = manager.path_for(
        DatasetKind.TRADING_ORDERS,
        symbol="session-1",
        freq="strategy-ai",
        timestamp=datetime(2024, 1, 2),
    )
    trades_path = manager.path_for(
        DatasetKind.TRADING_TRADES,
        symbol="session-1",
        freq="strategy-ai",
        timestamp=datetime(2024, 1, 2),
    )
    equity_path = manager.path_for(
        DatasetKind.TRADING_EQUITY,
        symbol="session-1",
        freq="strategy-ai",
        timestamp=datetime(2024, 1, 2),
    )

    orders_df = pd.read_parquet(orders_path)
    trades_df = pd.read_parquet(trades_path)
    equity_df = pd.read_parquet(equity_path)

    assert orders_df.shape[0] >= 1
    assert trades_df.shape[0] >= 1
    assert equity_df.iloc[-1]["equity"] <= session.account.total_equity()

    logs_dir = manager.directory_for(DatasetKind.STRATEGY_LLM_LOGS) / "strategy=strategy-ai" / "session=session-1"
    files = list(logs_dir.rglob("logs.jsonl"))
    assert files
    with files[0].open("r", encoding="utf-8") as fp:
        lines = fp.readlines()
    assert len(lines) >= 1
    entry = json.loads(lines[-1])
    assert entry["objective"] == "获取日内收益"
    assert "prompt" in entry
