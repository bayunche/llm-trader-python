"""受控交易调度任务测试。"""

from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.trading import ManagedTradingResult, RiskDecision, TradingSession, TradingSessionConfig
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


def test_run_cycle_accepts_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_run_managed(config, **_kwargs):
        captured["config"] = config
        return ManagedTradingResult(
            decision=RiskDecision(proceed=True, alerts=[]),
            raw_result={"orders_executed": 0, "trades_filled": 0},
        )

    monkeypatch.setattr("llm_trader.tasks.managed_cycle.run_managed_trading_cycle", fake_run_managed)

    config_payload = {
        "session_id": "session",
        "strategy_id": "strategy",
        "symbols": ["600000.SH"],
        "objective": "测试",
        "history_start": "2024-01-01T00:00:00",
        "history_end": "2024-01-02T00:00:00",
    }
    run_cycle(config_payload)

    assert isinstance(captured["config"], TradingCycleConfig)
    assert captured["config"].history_start == datetime(2024, 1, 1, 0, 0)


def test_run_cycle_passes_runtime_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    received = {}

    def fake_run_managed(config, *, generator=None, **_kwargs):
        received["generator"] = generator
        return ManagedTradingResult(
            decision=RiskDecision(proceed=True, alerts=[]),
            raw_result={"orders_executed": 0, "trades_filled": 0},
        )

    monkeypatch.setattr("llm_trader.tasks.managed_cycle.run_managed_trading_cycle", fake_run_managed)

    run_cycle(
        TradingCycleConfig(
            session_id="session",
            strategy_id="strategy",
            symbols=["600000.SH"],
            objective="测试",
            history_start=datetime(2024, 1, 1),
        ),
        generator="stub",
    )

    assert received["generator"] == "stub"
