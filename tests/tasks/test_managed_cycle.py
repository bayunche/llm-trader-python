"""受控交易调度任务测试。"""

from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.trading import TradingSession, TradingSessionConfig
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.trading.policy import RiskPolicy, RiskThresholds
from llm_trader.tasks.managed_cycle import run_cycle
from tests.trading.test_manager import ManagerFakeGenerator


def test_run_cycle(monkeypatch) -> None:
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
        }
    ]

    def fake_load(symbols, freq, start, end):
        return history

    monkeypatch.setattr(
        "llm_trader.trading.manager.run_ai_trading_cycle",
        lambda config, **kwargs: {
            "suggestion": ManagerFakeGenerator().generate(None),
            "quotes": [],
            "orders_executed": 0,
            "trades_filled": 0,
            "session": TradingSession(TradingSessionConfig(session_id="session", strategy_id="strategy")),
        },
    )

    config = TradingCycleConfig(
        session_id="session",
        strategy_id="strategy",
        symbols=["600000.SH"],
        objective="测试",
        history_start=datetime(2024, 1, 1),
    )
    policy = RiskPolicy(RiskThresholds(max_equity_drawdown=0.5, max_position_ratio=0.5))

    # 若函数能运行且无异常，即视为成功
    run_cycle(config, policy=policy)
