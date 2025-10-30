"""交易查询 API 测试。"""

from __future__ import annotations

from datetime import datetime
import json

from fastapi.testclient import TestClient

from llm_trader.api.app import app
from llm_trader.data import default_manager
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.strategy.logger import LLMStrategyLogRepository


client = TestClient(app)


def _prepare_trading_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    manager = default_manager()
    repo = ParquetRepository(manager=manager)
    dt = datetime(2024, 1, 2, 9, 30)

    orders = [
        {
            "order_id": "o-1",
            "symbol": "600000.SH",
            "side": "buy",
            "volume": 100,
            "price": 10.0,
            "status": "filled",
            "filled_volume": 100,
            "filled_amount": 1000.0,
            "created_at": dt,
        }
    ]
    repo.write_trading_orders("session-1", "strategy-ai", dt, orders)

    trades = [
        {
            "trade_id": "t-1",
            "order_id": "o-1",
            "symbol": "600000.SH",
            "side": "buy",
            "volume": 100,
            "price": 10.0,
            "fee": 5.0,
            "tax": 0.0,
            "timestamp": dt,
        }
    ]
    repo.write_trading_trades("session-1", "strategy-ai", dt, trades)

    snapshot = {
        "timestamp": dt,
        "cash": 99900.0,
        "equity": 100500.0,
        "positions": json.dumps(
            [
                {
                    "symbol": "600000.SH",
                    "volume": 100,
                    "cost_price": 10.0,
                }
            ],
            ensure_ascii=False,
        ),
    }
    repo.write_trading_equity("session-1", "strategy-ai", snapshot)

    log_repo = LLMStrategyLogRepository(manager=manager)
    log_repo.append(
        strategy_id="strategy-ai",
        session_id="session-1",
        prompt="prompt",
        response="response",
        payload={"symbols": ["600000.SH"], "objective": "test"},
        timestamp=dt,
    )


def test_trading_endpoints(tmp_path, monkeypatch) -> None:
    _prepare_trading_data(tmp_path, monkeypatch)
    monkeypatch.setenv("LLM_TRADER_API_KEY", "secret")
    headers = {"X-API-Key": "secret"}

    resp = client.get(
        "/api/trading/orders",
        params={"strategy_id": "strategy-ai", "session_id": "session-1"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["order_id"] == "o-1"

    resp = client.get(
        "/api/trading/trades",
        params={"strategy_id": "strategy-ai", "session_id": "session-1"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["trade_id"] == "t-1"

    resp = client.get(
        "/api/trading/equity",
        params={"strategy_id": "strategy-ai", "session_id": "session-1"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["equity"] == 100500.0

    resp = client.get(
        "/api/trading/logs",
        params={"strategy_id": "strategy-ai", "session_id": "session-1"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["objective"] == "test"
