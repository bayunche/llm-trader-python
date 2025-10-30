"""回测与策略 API 测试。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi.testclient import TestClient

from llm_trader.data import DatasetKind, default_manager
from llm_trader.strategy import StrategyRepository, StrategyVersion


def _prepare_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    manager = default_manager()
    symbols_path = manager.path_for(DatasetKind.SYMBOLS)
    df_symbols = pd.DataFrame(
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
    df_symbols.to_parquet(symbols_path, index=False)

    ohlcv_path = manager.path_for(
        DatasetKind.OHLCV_DAILY,
        symbol="600000.SH",
        freq="D",
        timestamp=datetime(2024, 7, 1),
    )
    df_ohlcv = pd.DataFrame(
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
            },
            {
                "symbol": "600000.SH",
                "dt": datetime(2024, 7, 2),
                "freq": "D",
                "open": 10.3,
                "high": 10.6,
                "low": 10.1,
                "close": 10.5,
                "volume": 110000,
                "amount": 1100000,
            },
        ]
    )
    df_ohlcv.to_parquet(ohlcv_path, index=False)


def _prepare_strategy() -> StrategyVersion:
    repo = StrategyRepository()
    version = StrategyVersion(
        strategy_id="demo",
        version_id="v1",
        run_id="run1",
        created_at=datetime.utcnow(),
        rules=[
            {
                "indicator": "sma",
                "column": "close",
                "params": {"window": 1},
                "operator": ">",
                "threshold": 10.0,
            }
        ],
        metrics={
            "total_return": 0.1,
            "annual_return": 0.1,
            "max_drawdown": -0.05,
            "sharpe_ratio": 1.2,
        },
    )
    repo.register_version(version)
    return version


def test_strategy_versions_endpoint(tmp_path, monkeypatch, api_client: TestClient) -> None:
    _prepare_data(tmp_path, monkeypatch)
    version = _prepare_strategy()
    response = api_client.get("/api/strategy/versions", params={"strategy_id": "demo"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["version_id"] == version.version_id


def test_backtest_run_endpoint(tmp_path, monkeypatch, api_client: TestClient) -> None:
    _prepare_data(tmp_path, monkeypatch)
    version = _prepare_strategy()
    body = {
        "strategy_id": "demo",
        "run_id": version.version_id,
        "symbols": ["600000.SH"],
        "start_date": "2024-07-01T00:00:00",
        "end_date": "2024-07-02T00:00:00",
        "initial_cash": 100000.0,
    }
    response = api_client.post("/api/backtest/run", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert "metrics" in payload["data"]
