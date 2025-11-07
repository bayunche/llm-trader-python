from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel, Session, create_engine, select

from llm_trader.decision import (
    DecisionService,
    ActorDecisionPayload,
    CheckerResultPayload,
)
from llm_trader.db.models.core import Observation
from llm_trader.db.models.enums import ClockPhase, RiskPosture
from llm_trader.db.models import Decision, DecisionAction, CheckerResult


def _session_factory(engine):
    def _factory():
        return Session(engine)

    return _factory


def test_decision_service_record_inserts_decision_and_actions():
    engine = create_engine("sqlite:///:memory:")
    if engine.dialect.name == "sqlite":
        pytest.skip("SQLite 不支持 JSONB，跳过决策服务入库测试")
    SQLModel.metadata.create_all(engine)
    factory = _session_factory(engine)

    generated_at = datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc)
    with factory() as session:
        session.add(
            Observation(
                observation_id="obs-1",
                generated_at=generated_at,
                valid_ttl_ms=3000,
                clock_phase=ClockPhase.CONTINUOUS_TRADING,
                account_nav=1_000_000.0,
                account_cash=500_000.0,
                account_risk_posture=RiskPosture.NORMAL,
                positions=[],
                universe=["600000.SH"],
                features={},
                market_rules={},
                risk_snapshot={},
            )
        )
        session.commit()

    actor_payload = ActorDecisionPayload.model_validate(
        {
            "decision_id": "dec-1",
            "timestamp": "2025-01-01T09:30:00Z",
            "observations_ref": "obs-1",
            "account_view": {"nav": 1_000_000.0, "cash": 500_000.0},
            "global_intent": {"risk_posture": "cautious", "max_new_margin": 100000.0},
            "actions": [
                {
                    "type": "place_order",
                    "symbol": "600000.SH",
                    "side": "buy",
                    "order_type": "limit",
                    "price": 10.5,
                    "qty": 100,
                    "tif": "day",
                    "intent_rationale": "测试",
                    "intent_confidence": 0.9,
                }
            ],
        }
    )
    checker_payload = CheckerResultPayload.model_validate(
        {
            "pass": True,
            "reasons": [],
            "observation_expired": False,
            "conflicts": [],
            "checked_at": "2025-01-01T09:30:05Z",
        }
    )

    service = DecisionService(session_factory=factory)
    record = service.record(
        observation_id="obs-1",
        actor_result=actor_payload,
        checker_result=checker_payload,
    )

    assert record.decision.decision_id == "dec-1"
    with factory() as session:
        stored_decision = session.get(Decision, "dec-1")
        assert stored_decision is not None
        actions = session.exec(
            select(DecisionAction).where(DecisionAction.decision_id == "dec-1")
        ).all()
        assert len(actions) == 1
        assert actions[0].symbol == "600000.SH"
        checker = session.get(CheckerResult, "dec-1")
        assert checker is not None
        assert checker.status.value == "pass"
