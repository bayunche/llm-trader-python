"""K 线管道测试。"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pyarrow.parquet as pq
import respx
from httpx import Response

from llm_trader.data import DataStoreManager, DatasetKind, default_manager
from llm_trader.data.pipelines.client import EastMoneyClient
from llm_trader.data.pipelines.ohlcv import OhlcvPipeline
from llm_trader.data.repositories.parquet import ParquetRepository


@respx.mock
def test_ohlcv_pipeline_sync_daily(tmp_path: Path) -> None:
    """应正确写入日线行情，并支持增量合并。"""

    respx.get("https://push2his.eastmoney.com/api/qt/stock/kline/get").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "klines": [
                        "2024-07-01,10.0,10.5,10.6,9.8,1000,1000000,0,0,0.5,0.1",
                        "2024-07-02,10.5,10.7,10.8,10.4,800,900000,0,0,0.4,0.08",
                    ]
                }
            },
        )
    )

    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    client = EastMoneyClient()
    pipeline = OhlcvPipeline(client=client, repository=repository)

    records = pipeline.sync(symbol="600000.SH", freq="D", start=date(2024, 7, 1), end=date(2024, 7, 2))
    client.close()

    assert len(records) == 2

    file_1 = manager.path_for(
        DatasetKind.OHLCV_DAILY,
        symbol="600000.SH",
        freq="D",
        timestamp=datetime(2024, 7, 1),
    )
    file_2 = manager.path_for(
        DatasetKind.OHLCV_DAILY,
        symbol="600000.SH",
        freq="D",
        timestamp=datetime(2024, 7, 2),
    )
    data_1 = pq.read_table(file_1).to_pylist()
    data_2 = pq.read_table(file_2).to_pylist()
    assert float(data_1[0]["close"]) == 10.5
    assert float(data_2[0]["close"]) == 10.7

    latest = repository.latest_timestamp("600000.SH", "D")
    assert latest is not None
