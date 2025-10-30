"""API 基础测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from llm_trader.api.security import reset_rate_limits


def test_health_check(api_client: TestClient) -> None:
    response = api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_requires_api_key_when_configured(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret-key")
    reset_rate_limits()

    response = api_client.get("/api/data/symbols")
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "E-SEC-401"

    headers = {"X-API-Key": "secret-key"}
    ok_response = api_client.get("/api/data/symbols", headers=headers)
    assert ok_response.status_code == 200


def test_rate_limit_enforced(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("LLM_TRADER_API_KEY", "limit-key")
    monkeypatch.setenv("LLM_TRADER_RATE_LIMIT", "1")
    reset_rate_limits()
    headers = {"X-API-Key": "limit-key"}

    first = api_client.get("/api/data/symbols", headers=headers)
    assert first.status_code == 200

    second = api_client.get("/api/data/symbols", headers=headers)
    assert second.status_code == 429
    assert second.json()["detail"]["error_code"] == "E-SEC-429"
