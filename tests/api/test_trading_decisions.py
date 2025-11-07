from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from llm_trader.api.app import app
from llm_trader.api.routes import trading
from llm_trader.db.models.enums import DecisionStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def _patch_decision_data(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    ledger_records = [
        type("Ledger", (), {
            "decision_id": "dec-1",
            "status": DecisionStatus.REJECTED_RISK,
            "observation_ref": "obs-1",
            "actor_model": "strategy-demo",
            "checker_model": "strategy-demo",
            "risk_summary": {"alerts": ["drawdown"]},
            "created_at": now,
            "executed_at": None,
        })()
    ]
    risk_map = {
        "dec-1": trading.RiskResultItem(
            decision_id="dec-1",
            passed=False,
            reasons=["drawdown"],
            corrections=[],
            evaluated_at=now,
        )
    }

    monkeypatch.setattr(
        trading,
        "_load_decision_records",
        lambda _session, **kwargs: ledger_records,
    )
    monkeypatch.setattr(
        trading,
        "_load_risk_map",
        lambda _session, ids: {k: risk_map.get(k) for k in ids},
    )
    yield
    monkeypatch.delenv("LLM_TRADER_API_KEY", raising=False)


def test_list_decisions_returns_ledger(monkeypatch):
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}
    resp = client.get("/api/trading/decisions?limit=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["data"][0]["decision_id"] == "dec-1"
    assert body["data"][0]["risk_result"]["passed"] is False


def test_get_decision_detail(monkeypatch):
    now = datetime.now(tz=timezone.utc)
    def fake_loader(session, did):
        return trading.DecisionDetailItem(
            decision_id="dec-1",
            status=DecisionStatus.EXECUTED,
            timestamp=now,
            observation_ref="obs-1",
            actor_model="actor",
            checker_model="checker",
            notes="test",
            actions=[
                trading.DecisionActionItem(
                    type="place_order",
                    symbol="600000.SH",
                    side="buy",
                    order_type="limit",
                    price=10.5,
                    qty=100,
                )
            ],
            checker_result=trading.CheckerResultItem(
                status="pass",
                reasons=[],
                observation_expired=False,
                checked_at=now,
            ),
                risk_result=trading.RiskResultItem(
                    decision_id="dec-1",
                    passed=True,
                    reasons=[],
                    corrections=[],
                    evaluated_at=now,
                ),
                ledger=None,
                llm_calls=[],
            )

    monkeypatch.setattr(trading, "_load_decision_detail", fake_loader)
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}
    resp = client.get("/api/trading/decisions/dec-1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["actions"][0]["symbol"] == "600000.SH"


def test_get_decision_detail_not_found(monkeypatch):
    monkeypatch.setattr(trading, "_load_decision_detail", lambda session, did: None)
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}
    resp = client.get("/api/trading/decisions/unknown", headers=headers)
    assert resp.status_code == 404
