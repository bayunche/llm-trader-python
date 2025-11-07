from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from llm_trader.api.app import app
from llm_trader.api.routes import config_models
from llm_trader.model_gateway.config import ModelEndpointSettings


client = TestClient(app)


@dataclass
class _StubGateway:
    settings: List[ModelEndpointSettings] | None = None
    metrics: List[Dict[str, object]] | None = None

    def update_settings(self, settings):  # noqa: D401
        self.settings = settings.endpoints

    def metrics_snapshot(self):  # noqa: D401
        return self.metrics or []


class _StubSession:
    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}

    def exec(self, statement):  # pragma: no cover - simple adapter
        class _Result(list):
            def all(self):
                return list(self)

        return _Result(self.store.values())

    def get(self, _model, key):
        return self.store.get(key)

    def add(self, obj):
        self.store[obj.model_alias] = obj

    def flush(self):  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch):
    stub_gateway = _StubGateway()
    stub_session = _StubSession()

    @dataclass
    class _StubModelEndpoint:
        model_alias: str
        provider: str
        endpoint_url: str
        auth_type: str
        auth_secret_ref: str
        default_params: Dict[str, Any]
        retry_policy: Dict[str, Any]
        routing: Dict[str, Any]
        circuit_breaker: Dict[str, Any]
        cost_estimate: Dict[str, Any]
        enabled: bool
        metadata: Dict[str, Any]
        created_at: datetime
        updated_at: datetime

    def fake_scope():
        class _Ctx:
            def __enter__(self):
                return stub_session

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()

    def fake_records_to_settings(records):
        return config_models.ModelGatewaySettings(
            enabled=True,
            default_model="gpt-4.1-mini",
            audit_enabled=True,
            endpoints=[ModelEndpointSettings(name=r.model_alias, base_url=r.endpoint_url, api_key=r.auth_secret_ref, weight=r.routing.get("weight", 1.0), timeout=r.retry_policy.get("timeout", 30.0), max_retries=r.retry_policy.get("max_retries", 2), enabled=r.enabled, prompt_cost_per_1k=r.cost_estimate.get("prompt_cost_per_1k", 0.0), completion_cost_per_1k=r.cost_estimate.get("completion_cost_per_1k", 0.0)) for r in records],
        )

    monkeypatch.setattr(config_models, "gateway", stub_gateway)
    monkeypatch.setattr(config_models, "ModelEndpoint", _StubModelEndpoint)
    monkeypatch.setattr(config_models, "select", lambda *args, **kwargs: None)
    monkeypatch.setattr(config_models, "session_scope", lambda: fake_scope())
    monkeypatch.setattr(config_models, "_records_to_settings", fake_records_to_settings)
    yield stub_gateway, stub_session
    monkeypatch.delenv("LLM_TRADER_API_KEY", raising=False)


def test_list_and_upsert_model_endpoint(_patch_dependencies, monkeypatch):
    stub_gateway, stub_session = _patch_dependencies
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}

    resp = client.get("/api/config/models", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []

    payload = {
        "model_alias": "gpt",
        "provider": "openai",
        "endpoint_url": "https://api.example.com",
        "auth_type": "api_key",
        "auth_secret_ref": "sk-test",
        "weight": 2.0,
        "timeout": 25.0,
        "max_retries": 1,
        "enabled": True,
        "prompt_cost_per_1k": 0.5,
        "completion_cost_per_1k": 1.5,
    }
    resp = client.put("/api/config/models", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["model_alias"] == "gpt"
    assert stub_gateway.settings and stub_gateway.settings[0].name == "gpt"

    resp = client.get("/api/config/models", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"][0]["model_alias"] == "gpt"


def test_metrics_endpoint(_patch_dependencies, monkeypatch):
    stub_gateway, _ = _patch_dependencies
    stub_gateway.metrics = [
        {
            "endpoint": "mock",
            "enabled": True,
            "available": True,
            "success_count": 3,
            "failure_count": 1,
            "consecutive_failures": 0,
            "opened_until": None,
            "last_error": None,
        }
    ]
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}
    resp = client.get("/api/config/models/metrics", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"][0]["endpoint"] == "mock"
