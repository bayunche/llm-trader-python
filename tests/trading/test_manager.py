"""受控交易执行测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from llm_trader.decision import ActorDecisionPayload
from llm_trader.trading import TradingSessionConfig
from llm_trader.trading.manager import run_managed_trading_cycle
from llm_trader.trading.policy import RiskDecision, RiskPolicy, RiskThresholds
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
            selected_symbols=["600000.SH"],
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


def test_run_managed_trading_cycle_records_risk(monkeypatch) -> None:
    actor_payload = ActorDecisionPayload.model_validate(
        {
            "decision_id": "dec-test",
            "timestamp": "2025-01-01T09:30:00Z",
            "observations_ref": "obs-1",
            "account_view": {"nav": 1000000, "cash": 500000},
            "actions": [
                {
                    "type": "place_order",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "order_type": "limit",
                    "price": 10.5,
                    "qty": 100,
                    "tif": "day",
                }
            ],
        }
    )

    session = TradingSession(TradingSessionConfig(session_id="session", strategy_id="strategy"))

    def fake_run_ai(config, **kwargs):
        return {
            "session": session,
            "decision": actor_payload,
            "decision_record": SimpleNamespace(decision=SimpleNamespace(decision_id="dec-test"), checker_result=None),
            "checker_result": None,
        }

    class StubDecisionService:
        def __init__(self) -> None:
            self.risk_args = None
            self.ledger_args = None

        def record_risk_result(self, **kwargs):
            self.risk_args = kwargs
            return SimpleNamespace(**kwargs)

        def record_ledger(self, **kwargs):
            self.ledger_args = kwargs
            return SimpleNamespace(**kwargs)

    monkeypatch.setattr("llm_trader.trading.manager.run_ai_trading_cycle", fake_run_ai)
    decision_service = StubDecisionService()

    outcome = run_managed_trading_cycle(
        TradingCycleConfig(
            session_id="session",
            strategy_id="strategy",
            symbols=["600000.SH"],
            objective="测试",
            history_start=datetime(2024, 1, 1),
        ),
        decision_service=decision_service,
    )

    assert outcome.decision.proceed
    assert decision_service.risk_args is not None
    assert decision_service.risk_args["decision_id"] == "dec-test"
    assert decision_service.ledger_args is not None
    assert decision_service.ledger_args["decision_id"] == "dec-test"


def test_run_managed_trading_cycle_emits_alert(monkeypatch) -> None:
    monkeypatch.setenv("TRADING_EXECUTION_MODE", "sandbox")
    _captured = {}

    def fake_emit(self, message, *, details=None):
        _captured["message"] = message
        _captured["details"] = details or {}

    monkeypatch.setattr("llm_trader.trading.manager.AlertEmitter.emit", fake_emit, raising=False)

    policy = RiskPolicy(RiskThresholds(max_equity_drawdown=0.0, max_position_ratio=0.0))
    session = TradingSession(TradingSessionConfig(session_id="s", strategy_id="st"))

    def fake_run(*_args, **_kwargs):
        return {
            "session": session,
        }

    monkeypatch.setattr("llm_trader.trading.manager.run_ai_trading_cycle", fake_run)

    decision = RiskDecision(proceed=False, alerts=["test alert"])
    monkeypatch.setattr(
        "llm_trader.trading.manager.RiskPolicy.evaluate",
        lambda self, *_args, **_kwargs: decision,
    )

    result = run_managed_trading_cycle(TradingCycleConfig(session_id="s", strategy_id="st", symbols=[], objective=""), policy=policy)
    assert not result.decision.proceed
    assert _captured["details"]["reason"] == "test alert"
