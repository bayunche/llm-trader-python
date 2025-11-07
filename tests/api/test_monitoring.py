from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from llm_trader.api.app import app
from llm_trader.api.routes import monitoring
from llm_trader.db.models.enums import ModelRole

client = TestClient(app)


@dataclass
class _StubAudit:
    trace_id: str
    decision_id: str | None
    role: ModelRole
    provider: str
    model: str
    tokens_prompt: int
    tokens_completion: int
    latency_ms: int
    cost: float
    created_at: datetime


class _StubSession:
    def __init__(self, records: List[_StubAudit]) -> None:
        self.records = records
        self.statements: List[Any] = []

    def exec(self, statement):
        self.statements.append(statement)

        class _Result(list):
            def all(self_self):
                return list(self_self)

        result = _Result()
        result.extend(self.records)
        return result


@pytest.fixture(autouse=True)
def _patch_monitoring_session(monkeypatch: pytest.MonkeyPatch):
    records = [
        _StubAudit(
            trace_id="trace-1",
            decision_id="dec-1",
            role=ModelRole.ACTOR,
            provider="openai",
            model="gpt-4.1-mini",
            tokens_prompt=100,
            tokens_completion=20,
            latency_ms=800,
            cost=0.012,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    ]
    stub_session = _StubSession(records)

    def fake_scope():
        class _Ctx:
            def __enter__(self):
                return stub_session

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()

    monkeypatch.setattr(monitoring, "session_scope", lambda: fake_scope())
    yield stub_session
    monkeypatch.delenv("LLM_TRADER_API_KEY", raising=False)


def test_list_llm_calls_returns_records(_patch_monitoring_session, monkeypatch):
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}
    resp = client.get("/api/monitor/llm-calls?role=actor&limit=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "OK"
    assert body["data"][0]["trace_id"] == "trace-1"
    assert body["data"][0]["role"] == "actor"
