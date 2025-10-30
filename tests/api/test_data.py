"""数据接口测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from llm_trader.data import DatasetKind, default_manager


def _prepare_symbols(tmp_path: Path) -> None:
    manager = default_manager()
    path = manager.path_for(DatasetKind.SYMBOLS)
    df = pd.DataFrame(
        [
            {
                "symbol": "600000.SH",
                "name": "浦发银行",
                "board": "主板",
                "status": "active",
                "listed_date": datetime(1999, 11, 10),
                "delisted_date": None,
            }
        ]
    )
    df.to_parquet(path, index=False)


def _prepare_ohlcv(tmp_path: Path) -> None:
    manager = default_manager()
    path = manager.path_for(
        DatasetKind.OHLCV_DAILY,
        symbol="600000.SH",
        freq="D",
        timestamp=datetime(2024, 7, 1),
    )
    df = pd.DataFrame(
        [
            {
                "symbol": "600000.SH",
                "dt": datetime(2024, 7, 1),
                "freq": "D",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 100000,
                "amount": 1000000,
            }
        ]
    )
    df.to_parquet(path, index=False)


def test_list_symbols_returns_data(tmp_path, monkeypatch, api_client: TestClient) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    _prepare_symbols(tmp_path)
    response = api_client.get("/api/data/symbols")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["symbol"] == "600000.SH"


def test_list_ohlcv_returns_data(tmp_path, monkeypatch, api_client: TestClient) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    _prepare_ohlcv(tmp_path)
    response = api_client.get("/api/data/ohlcv", params={"symbol": "600000.SH"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["close"] == 10.2
