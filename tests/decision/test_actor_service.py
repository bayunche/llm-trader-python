from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from llm_trader.decision.actor import ActorContext, ActorService
from llm_trader.decision.checker import CheckerContext, CheckerService
from llm_trader.decision.schema import ActorDecisionPayload
from llm_trader.model_gateway.service import GatewayResponse


@dataclass
class _StubGateway:
    payload: dict

    def chat_completions(self, request_body, *, decision_id, role, model=None):  # noqa: D401
        return GatewayResponse(payload=self.payload, endpoint=None, latency_ms=10)

    def close(self):  # pragma: no cover - no-op
        pass


def _sample_observation() -> Dict[str, Any]:
    return {
        "observation_id": "obs-1",
        "generated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "valid_ttl_ms": 3000,
        "clock": {"phase": "continuous_trading"},
        "account": {"nav": 1_000_000.0, "cash": 500_000.0},
        "positions": [],
        "universe": ["600000.SH"],
        "features": {},
        "market_rules": {},
        "risk_snapshot": {"posture": "normal"},
    }


def test_actor_service_parses_decision():
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": """
                    {
                        \"decision_id\": \"dec-1\",
                        \"timestamp\": \"2025-01-01T09:30:00Z\",
                        \"observations_ref\": \"obs-1\",
                        \"account_view\": {\"nav\": 1000000, \"cash\": 500000},
                        \"actions\": [
                            {
                                \"type\": \"place_order\",
                                \"symbol\": \"600000.SH\",
                                \"side\": \"buy\",
                                \"order_type\": \"limit\",
                                \"price\": 10.5,
                                \"qty\": 100,
                                \"tif\": \"day\",
                                \"intent_rationale\": \"测试\",
                                \"intent_confidence\": 0.8
                            }
                        ]
                    }
                    """,
                }
            }
        ],
    }
    gateway = _StubGateway(response_payload)
    actor = ActorService(gateway)
    context = ActorContext(session_id="session", strategy_id="strategy", objective="demo")
    decision = actor.generate_decision(_sample_observation(), context=context)

    assert isinstance(decision, ActorDecisionPayload)
    assert decision.decision_id == "dec-1"
    assert decision.actions[0].symbol == "600000.SH"


def test_checker_service_parses_result():
    checker_response = {
        "choices": [
            {
                "message": {
                    "content": """
                    {\"pass\": true, \"reasons\": [], \"observation_expired\": false, \"conflicts\": [], \"checked_at\": \"2025-01-01T09:31:00Z\"}
                    """
                }
            }
        ]
    }
    gateway = _StubGateway(checker_response)
    checker = CheckerService(gateway)

    decision = ActorDecisionPayload.model_validate(
        {
            "decision_id": "dec-1",
            "timestamp": "2025-01-01T09:30:00Z",
            "observations_ref": "obs-1",
            "account_view": {"nav": 1000000, "cash": 500000},
            "actions": [
                {
                    "type": "no_op",
                    "intent_confidence": 0.0,
                }
            ],
        }
    )

    result = checker.review(_sample_observation(), decision.model_dump(), context=CheckerContext(session_id="s", strategy_id="st"))
    assert result.passed is True
    assert not result.reasons
    assert result.checked_at is not None


def test_actor_service_raises_on_invalid_response():
    gateway = _StubGateway({"choices": [{"message": {"content": "{}"}}]})
    actor = ActorService(gateway)
    context = ActorContext(session_id="session", strategy_id="strategy", objective="demo")
    with pytest.raises(Exception):
        actor.generate_decision(_sample_observation(), context=context)
