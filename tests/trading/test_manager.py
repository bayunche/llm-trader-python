"""受控交易执行测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.trading import TradingSessionConfig
from llm_trader.trading.manager import run_managed_trading_cycle
from llm_trader.trading.policy import RiskPolicy, RiskThresholds
from llm_trader.trading.session import TradingSession
from tests.trading.test_orchestrator import FakeRealtimePipeline
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.strategy.engine import RuleConfig
from llm_trader.strategy.llm_generator import LLMStrategySuggestion


class ManagerFakeGenerator:
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
                    threshold=8.5,
                )
            ],
        )

    def generate(self, context):
        return self._suggestion


def test_run_managed_trading_cycle_triggers_policy(monkeypatch) -> None:
    history = [
        {
            "symbol": "600000.SH",
            "dt": datetime(2024, 1, 1, 9, 30),
            "freq": "D",
            "open": 10.0,
            "high": 10.2,
            "low": 9.8,
            "close": 10.1,
            "volume": 100000,
            "amount": 1000000,
        },
        {
            "symbol": "600000.SH",
            "dt": datetime(2024, 1, 2, 9, 30),
            "freq": "D",
            "open": 9.0,
            "high": 9.1,
            "low": 8.8,
            "close": 8.9,
            "volume": 120000,
            "amount": 1000000,
        },
    ]

    def fake_load(symbols, freq, start, end):
        return history

    generator = ManagerFakeGenerator()
    realtime = FakeRealtimePipeline(
        [
            {
                "symbol": "600000.SH",
                "last_price": 9.0,
                "change_ratio": -5.0,
            }
        ]
    )
    session = TradingSession(
        TradingSessionConfig(session_id="session", strategy_id="strategy", initial_cash=1000.0)
    )
    config = TradingCycleConfig(
        session_id="session",
        strategy_id="strategy",
        symbols=["600000.SH"],
        objective="测试",
        indicators=("sma",),
        history_start=datetime(2024, 1, 1),
        initial_cash=1000.0,
    )
    policy = RiskPolicy(RiskThresholds(max_equity_drawdown=0.01, max_position_ratio=0.1))

    outcome = run_managed_trading_cycle(
        config,
        policy=policy,
        trading_session=session,
        generator=generator,
        realtime_pipeline=realtime,
        load_ohlcv_fn=fake_load,
    )
    assert not outcome.decision.proceed
    assert outcome.decision.alerts
