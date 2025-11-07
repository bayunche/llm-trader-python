from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from llm_trader.model_gateway.config import ModelEndpointSettings
from llm_trader.model_gateway.loader import (
    build_gateway_settings_from_records,
    load_gateway_settings,
)


@dataclass
class _StubEndpoint:
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


def _sample_endpoint(**overrides: Any) -> _StubEndpoint:
    now = datetime.now(tz=timezone.utc)
    payload: Dict[str, Any] = {
        "model_alias": "gpt",
        "provider": "openai",
        "endpoint_url": "https://api.example.com",
        "auth_type": "api_key",
        "auth_secret_ref": "sk-test",
        "default_params": {"temperature": 0.1},
        "retry_policy": {"timeout": 20.0, "max_retries": 1},
        "routing": {"weight": 2.0},
        "circuit_breaker": {"failure_threshold": 2, "recovery_seconds": 30},
        "cost_estimate": {"prompt_cost_per_1k": 0.5, "completion_cost_per_1k": 1.5},
        "enabled": True,
        "metadata": {"X-Test": "1"},
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return _StubEndpoint(**payload)


def test_build_gateway_settings_from_records() -> None:
    record = _sample_endpoint()
    settings = build_gateway_settings_from_records([record])
    assert settings.endpoints
    endpoint: ModelEndpointSettings = settings.endpoints[0]
    assert endpoint.name == "gpt"
    assert endpoint.base_url == "https://api.example.com"
    assert endpoint.weight == 2.0
    assert endpoint.prompt_cost_per_1k == 0.5
    assert endpoint.headers == {"X-Test": "1"}


def test_load_gateway_settings_fallback_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenFactory:
        def __call__(self):
            raise RuntimeError("boom")

    broken_factory = _BrokenFactory()
    settings = load_gateway_settings(broken_factory)
    from llm_trader.config import get_settings

    assert settings == get_settings().model_gateway


def test_load_gateway_settings_uses_db_records(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [_sample_endpoint(model_alias="claude", endpoint_url="https://claude.local")]

    class _StubResult(list):
        def all(self) -> List[ModelEndpoint]:
            return list(self)

    class _StubSession:
        def __init__(self):
            self.records = records

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def exec(self, statement):
            return _StubResult(self.records)

    class _Factory:
        def __call__(self):
            return _StubSession()

    settings = load_gateway_settings(_Factory())
    assert settings.endpoints[0].name == "claude"
