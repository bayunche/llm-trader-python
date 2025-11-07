from __future__ import annotations

import respx
from httpx import Response
import pytest

from llm_trader.db.models.enums import ModelRole
from llm_trader.model_gateway import ModelEndpointSettings, ModelGateway, ModelGatewaySettings


class _StubSession:
    def __init__(self) -> None:
        self.records = []

    def add(self, obj) -> None:  # pragma: no cover - simple container
        self.records.append(obj)


class _StubSessionFactory:
    def __init__(self) -> None:
        self.session = _StubSession()

    def __call__(self):
        session = self.session

        class _Ctx:
            def __enter__(self):  # pragma: no cover - trivial
                return session

            def __exit__(self, exc_type, exc, tb):  # pragma: no cover - trivial
                return False

        return _Ctx()


class _StubAudit:
    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


@respx.mock
def test_chat_completions_records_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = ModelEndpointSettings(name="mock", base_url="https://mock-llm", api_key="sk-test")
    settings = ModelGatewaySettings(endpoints=[endpoint])
    factory = _StubSessionFactory()
    monkeypatch.setattr("llm_trader.model_gateway.service.LLMCallAudit", _StubAudit)
    gateway = ModelGateway(settings=settings, session_factory=factory)

    respx.post("https://mock-llm/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {"role": "assistant", "content": "OK"},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )
    )

    payload = {"messages": [{"role": "user", "content": "hi"}]}
    result = gateway.chat_completions(payload, decision_id="dec-1", role=ModelRole.ACTOR)
    gateway.close()

    assert result.payload["choices"][0]["message"]["content"] == "OK"
    assert factory.session.records  # 确认已写入审计

    audit_entry = factory.session.records[0]
    assert audit_entry.decision_id == "dec-1"
    assert audit_entry.provider == "mock"
    assert audit_entry.model == settings.default_model
    assert audit_entry.tokens_prompt == 10
    assert audit_entry.tokens_completion == 5


@respx.mock
def test_chat_completions_fallback_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoints = [
        ModelEndpointSettings(name="fail", base_url="https://fail-llm"),
        ModelEndpointSettings(name="ok", base_url="https://ok-llm"),
    ]
    settings = ModelGatewaySettings(endpoints=endpoints)
    factory = _StubSessionFactory()
    monkeypatch.setattr("llm_trader.model_gateway.service.LLMCallAudit", _StubAudit)
    gateway = ModelGateway(settings=settings, session_factory=factory)

    respx.post("https://fail-llm/v1/chat/completions").mock(return_value=Response(500, json={"error": "boom"}))
    respx.post("https://ok-llm/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "id": "chatcmpl-2",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {"role": "assistant", "content": "FALLBACK"},
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 2},
            },
        )
    )

    payload = {"messages": [{"role": "user", "content": "fallback"}]}
    result = gateway.chat_completions(payload, role=ModelRole.CHECKER)
    gateway.close()

    assert result.endpoint.name == "ok"
    assert result.payload["choices"][0]["message"]["content"] == "FALLBACK"
    assert factory.session.records  # 确认仍然写入审计

    recorded = factory.session.records[0]
    assert isinstance(recorded.prompt_hash, str)
