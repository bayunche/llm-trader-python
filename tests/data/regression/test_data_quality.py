"""数据质量回归测试。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from llm_trader.data import DatasetKind, default_manager
from llm_trader.data.repositories.parquet import ParquetRepository


@pytest.fixture
def regression_repo(tmp_path: Path) -> ParquetRepository:
    manager = default_manager(base_dir=tmp_path / "data_store")
    repo = ParquetRepository(manager=manager)
    # 构造基础样本
    repo.write_symbols([
        {"symbol": "600000.SH", "name": "浦发银行", "exchange": "SH"},
        {"symbol": "000001.SZ", "name": "平安银行", "exchange": "SZ"},
    ])
    repo.write_trading_calendar([
        {"date": "2024-01-02", "is_trading": True},
        {"date": "2024-01-03", "is_trading": False},
    ])
    repo.write_ohlcv_daily(
        "600000.SH",
        "D",
        [
            {
                "date": "2024-01-02",
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 100000,
                "amount": 1000000,
            }
        ],
    )
    repo.write_trading_orders(
        "session-demo",
        "strategy-demo",
        datetime.fromisoformat("2024-01-02T09:30:00"),
        [
            {
                "order_id": "order-1",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.2,
                "status": "filled",
                "filled_volume": 100,
                "filled_amount": 1020.0,
                "created_at": datetime.fromisoformat("2024-01-02T09:30:00"),
            }
        ],
    )
    return repo


def _read_parquet(path: Path) -> list:
    table = pq.read_table(path)
    return table.to_pylist()


def test_symbol_dataset_structure(regression_repo: ParquetRepository) -> None:
    manager = regression_repo.manager
    config = manager.get(DatasetKind.SYMBOLS)
    path = manager.base_dir / config.relative_dir / config.filename_template
    records = _read_parquet(path)
    assert any(rec["symbol"] == "600000.SH" for rec in records)
    assert all("exchange" in rec for rec in records)


def test_calendar_dataset_consistency(regression_repo: ParquetRepository) -> None:
    manager = regression_repo.manager
    config = manager.get(DatasetKind.TRADING_CALENDAR)
    path = manager.base_dir / config.relative_dir / config.filename_template
    records = _read_parquet(path)
    trading_days = [rec["date"] for rec in records if rec["is_trading"]]
    assert "2024-01-02" in trading_days


def test_order_dataset_partition(regression_repo: ParquetRepository) -> None:
    manager = regression_repo.manager
    config = manager.get(DatasetKind.TRADING_ORDERS)
    partition = config.render_partition({"symbol": "session-demo", "freq": "strategy-demo", "date": "20240102"})
    path = manager.base_dir / config.relative_dir / partition / config.filename_template.format()
    assert path.exists()
