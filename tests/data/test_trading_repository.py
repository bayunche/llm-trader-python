"""交易数据仓储单元测试。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from llm_trader.data import DatasetKind, default_manager
from llm_trader.data.repositories.parquet import ParquetRepository


def _build_repository(tmp_path) -> ParquetRepository:
    base_dir = tmp_path / "data_store"
    manager = default_manager(base_dir=base_dir)
    return ParquetRepository(manager=manager)


def test_write_trading_orders_merges_by_order_id(tmp_path) -> None:
    repo = _build_repository(tmp_path)
    dt = datetime(2024, 1, 1, 9, 30)
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
    repo.write_trading_orders("session-a", "strategy-x", dt, orders)
    # 再次写入同一订单，验证去重逻辑
    repo.write_trading_orders("session-a", "strategy-x", dt, orders)

    manager = repo.manager
    path = manager.path_for(DatasetKind.TRADING_ORDERS, symbol="session-a", freq="strategy-x", timestamp=dt)
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.iloc[0]["order_id"] == "o-1"


def test_write_trading_trades_records(tmp_path) -> None:
    repo = _build_repository(tmp_path)
    dt = datetime(2024, 1, 1, 9, 35)
    trades = [
        {
            "trade_id": "t-1",
            "order_id": "o-1",
            "symbol": "600000.SH",
            "side": "buy",
            "volume": 100,
            "price": 10.0,
            "fee": 1.0,
            "tax": 0.0,
            "timestamp": dt,
        }
    ]
    repo.write_trading_trades("session-a", "strategy-x", dt, trades)

    manager = repo.manager
    path = manager.path_for(DatasetKind.TRADING_TRADES, symbol="session-a", freq="strategy-x", timestamp=dt)
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert df.iloc[0]["trade_id"] == "t-1"


def test_write_trading_equity_appends(tmp_path) -> None:
    repo = _build_repository(tmp_path)
    dt = datetime(2024, 1, 1, 9, 40)
    snapshot = {
        "timestamp": dt,
        "cash": 100000.0,
        "equity": 100500.0,
        "positions": "[]",
    }
    repo.write_trading_equity("session-a", "strategy-x", snapshot)

    later = {
        "timestamp": dt.replace(hour=10, minute=0),
        "cash": 100200.0,
        "equity": 100800.0,
        "positions": "[]",
    }
    repo.write_trading_equity("session-a", "strategy-x", later)

    manager = repo.manager
    path = manager.path_for(
        DatasetKind.TRADING_EQUITY,
        symbol="session-a",
        freq="strategy-x",
        timestamp=later["timestamp"],
    )
    df = pd.read_parquet(path)
    assert len(df) == 2
    assert df.iloc[-1]["equity"] == later["equity"]


def test_write_trading_run_summary(tmp_path) -> None:
    repo = _build_repository(tmp_path)
    dt = datetime(2024, 1, 1, 9, 45)
    repo.write_trading_run_summary(
        strategy_id="strategy-ai",
        session_id="session-a",
        record={
            "timestamp": dt,
            "strategy_id": "strategy-ai",
            "session_id": "session-a",
            "status": "executed",
            "decision_proceed": True,
            "alerts": json.dumps([]),
            "orders_executed": 2,
            "trades_filled": 1,
            "selected_symbols": json.dumps(["600000.SH"]),
            "suggestion_description": "demo summary",
            "rules": json.dumps([{"indicator": "sma"}]),
            "llm_prompt": "prompt",
            "llm_response": json.dumps({"rules": []}),
            "objective": "测试",
            "indicators": json.dumps(["sma"]),
        },
    )
    path = repo.manager.path_for(
        DatasetKind.TRADING_RUNS,
        symbol="strategy-ai",
        freq="session-a",
        ensure_dir=False,
    )
    df = pd.read_parquet(path)
    assert df.shape[0] == 1
    assert df.iloc[0]["orders_executed"] == 2
    assert df.iloc[0]["status"] == "executed"
