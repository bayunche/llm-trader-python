"""受控交易调度任务测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.trading import ManagedTradingResult, RiskDecision, TradingSession, TradingSessionConfig
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.trading.policy import RiskPolicy, RiskThresholds
import llm_trader.tasks.managed_cycle as managed_cycle
from llm_trader.tasks.managed_cycle import run_cycle
from tests.trading.test_manager import ManagerFakeGenerator


class _StubDataService:
    def sync_master_symbols(self):
        return []

    def sync_account_snapshot(self):
        return None

    def sync_realtime_quotes(self, _symbols):
        return []


class _StubObservation:
    observation_id = "obs-1"
    universe = []

    def to_dict(self):
        return {
            "observation_id": self.observation_id,
            "generated_at": datetime.utcnow().isoformat(),
            "valid_ttl_ms": 3000,
            "clock": {"phase": "continuous_trading"},
            "account": {"nav": 1000000.0, "cash": 500000.0},
            "positions": [],
            "universe": [],
            "features": {},
            "market_rules": {},
            "risk_snapshot": {},
        }


class _StubObservationBuilder:
    cache_metrics = {"hits": 0, "misses": 1}

    def build(self):
        return _StubObservation()


class _DummyDataService:
    def __init__(self, *args, **kwargs):
        pass

    def sync_master_symbols(self):
        return []

    def sync_account_snapshot(self):
        return None

    def sync_realtime_quotes(self, _symbols):
        return []


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
    monkeypatch.setattr(managed_cycle, "_ensure_services", lambda _limit: (_StubDataService(), _StubObservationBuilder()))
    monkeypatch.setattr(managed_cycle, "_ensure_decision_services", lambda _factory: (None, None, None))
    monkeypatch.setattr(managed_cycle, "_DATA_SERVICE", _StubDataService())
    monkeypatch.setattr(managed_cycle, "_OBSERVATION_BUILDER", _StubObservationBuilder())
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_account_snapshot",
        lambda self: None,
    )
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_master_symbols",
        lambda self: [],
    )
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_realtime_quotes",
        lambda self, _symbols: [],
    )
    monkeypatch.setattr("llm_trader.data.ingestion.service.DataIngestionService", _DummyDataService)
    monkeypatch.setattr(managed_cycle, "DataIngestionService", _DummyDataService)

    config = TradingCycleConfig(
        session_id="session",
        strategy_id="strategy",
        symbols=["600000.SH"],
        objective="测试",
        history_start=datetime(2024, 1, 1),
    )
    policy = RiskPolicy(RiskThresholds(max_equity_drawdown=0.5, max_position_ratio=0.5))

    # 若函数能运行且无异常，即视为成功
    run_cycle(
        config,
        policy=policy,
        data_service=_StubDataService(),
        observation_builder=_StubObservationBuilder(),
    )


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
    run_cycle(
        config_payload,
        data_service=_StubDataService(),
        observation_builder=_StubObservationBuilder(),
    )

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
        data_service=_StubDataService(),
        observation_builder=_StubObservationBuilder(),
    )

    assert received["generator"] == "stub"


def test_ensure_trading_config_with_lookback(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_now = datetime(2024, 1, 10, 0, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):  # noqa: D401 - 简单重写
            return fixed_now

    monkeypatch.setattr("llm_trader.tasks.managed_cycle.datetime", FrozenDateTime)
    monkeypatch.setattr("llm_trader.tasks.managed_cycle.timedelta", timedelta)

    config = managed_cycle._ensure_trading_config(  # pylint: disable=protected-access
        {
            "session_id": "session",
            "strategy_id": "strategy",
            "symbols": [],
            "objective": "测试",
            "lookback_days": 5,
        }
    )

    assert config.history_end == fixed_now
    assert config.history_start == fixed_now - timedelta(days=5)


def test_sync_account_snapshot_job(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {}

    class DummyService:
        def sync_account_snapshot(self):
            calls["called"] = True

    def fake_ensure_services(_limit):
        return DummyService(), object()

    monkeypatch.setattr("llm_trader.tasks.managed_cycle._ensure_services", fake_ensure_services)
    managed_cycle.sync_account_snapshot()

    assert calls["called"] is True
    monkeypatch.setattr(managed_cycle, "_ensure_services", lambda _limit: (_StubDataService(), _StubObservationBuilder()))
    monkeypatch.setattr(managed_cycle, "_ensure_decision_services", lambda _factory: (None, None, None))
    monkeypatch.setattr(managed_cycle, "_DATA_SERVICE", _StubDataService())
    monkeypatch.setattr(managed_cycle, "_OBSERVATION_BUILDER", _StubObservationBuilder())
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_account_snapshot",
        lambda self: None,
    )
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_master_symbols",
        lambda self: [],
    )
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_realtime_quotes",
        lambda self, _symbols: [],
    )
    monkeypatch.setattr("llm_trader.data.ingestion.service.DataIngestionService", _DummyDataService)
    monkeypatch.setattr(managed_cycle, "DataIngestionService", _DummyDataService)
    monkeypatch.setattr(managed_cycle, "_ensure_services", lambda _limit: (_StubDataService(), _StubObservationBuilder()))
    monkeypatch.setattr(managed_cycle, "_ensure_decision_services", lambda _factory: (None, None, None))
    monkeypatch.setattr(managed_cycle, "_DATA_SERVICE", _StubDataService())
    monkeypatch.setattr(managed_cycle, "_OBSERVATION_BUILDER", _StubObservationBuilder())
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_account_snapshot",
        lambda self: None,
    )
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_master_symbols",
        lambda self: [],
    )
    monkeypatch.setattr(
        "llm_trader.data.ingestion.service.DataIngestionService.sync_realtime_quotes",
        lambda self, _symbols: [],
    )
    monkeypatch.setattr("llm_trader.data.ingestion.service.DataIngestionService", _DummyDataService)
    monkeypatch.setattr(managed_cycle, "DataIngestionService", _DummyDataService)
