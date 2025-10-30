"""全链路自动交易测试。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from llm_trader.pipeline.auto import BacktestCriteria, AutoTradingConfig, run_full_automation
from llm_trader.trading import TradingCycleConfig, ManagedTradingResult, TradingSession, TradingSessionConfig, RiskDecision
from llm_trader.strategy.llm_generator import LLMStrategySuggestion
from llm_trader.strategy.engine import RuleConfig


class PipelineFakeGenerator:
    def __init__(self) -> None:
        self.last_prompt = "prompt"
        self.last_raw_response = "response"
        self._suggestion = LLMStrategySuggestion(
            description="test",
            rules=[
                RuleConfig(
                    indicator="sma",
                    column="close",
                    params={"window": 1},
                    operator=">",
                    threshold=9.0,
                )
            ],
        )

    def generate(self, context):
        return self._suggestion


def _load_mock_bars(*_args, **_kwargs):
    return [
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
            "close": 10.6,
            "volume": 120000,
            "amount": 1230000,
        },
    ]


def test_full_automation_executes(monkeypatch) -> None:
    config = AutoTradingConfig(
        trading=TradingCycleConfig(
            session_id="session",
            strategy_id="strategy",
            symbols=["600000.SH"],
            objective="测试",
            indicators=("sma",),
            history_start=datetime(2024, 1, 1),
        ),
        backtest_start=datetime(2024, 1, 1),
        backtest_end=datetime(2024, 1, 2),
        criteria=BacktestCriteria(min_total_return=-0.1, max_drawdown=0.5),
    )

    def fake_cycle(*_args, **kwargs):
        session = kwargs.get("trading_session") or TradingSession(
            TradingSessionConfig(session_id="session", strategy_id="strategy")
        )
        return {
            "suggestion": PipelineFakeGenerator().generate(None),
            "quotes": [],
            "orders_executed": 0,
            "trades_filled": 0,
            "session": session,
        }

    monkeypatch.setattr("llm_trader.pipeline.auto.run_ai_trading_cycle", fake_cycle)

    managed_result = ManagedTradingResult(
        decision=RiskDecision(proceed=True, alerts=[]),
        raw_result={
            "orders_executed": 1,
            "trades_filled": 1,
            "session": TradingSession(TradingSessionConfig(session_id="session", strategy_id="strategy")),
        },
    )

    monkeypatch.setattr("llm_trader.pipeline.auto.run_managed_trading_cycle", lambda *args, **kwargs: managed_result)

    result = run_full_automation(config, load_ohlcv_fn=_load_mock_bars)
    assert result.status == "executed"
    assert result.backtest_metrics is not None


def test_full_automation_rejects_on_backtest(monkeypatch) -> None:
    config = AutoTradingConfig(
        trading=TradingCycleConfig(
            session_id="session",
            strategy_id="strategy",
            symbols=["600000.SH"],
            objective="测试",
            indicators=("sma",),
            history_start=datetime(2024, 1, 1),
        ),
        backtest_start=datetime(2024, 1, 1),
        backtest_end=datetime(2024, 1, 2),
        criteria=BacktestCriteria(min_total_return=0.5, max_drawdown=0.1),
    )

    def fake_cycle(*_args, **kwargs):
        session = kwargs.get("trading_session") or TradingSession(
            TradingSessionConfig(session_id="session", strategy_id="strategy")
        )
        return {
            "suggestion": PipelineFakeGenerator().generate(None),
            "quotes": [],
            "orders_executed": 0,
            "trades_filled": 0,
            "session": session,
        }

    monkeypatch.setattr("llm_trader.pipeline.auto.run_ai_trading_cycle", fake_cycle)

    result = run_full_automation(config, load_ohlcv_fn=_load_mock_bars)
    assert result.status == "backtest_rejected"
