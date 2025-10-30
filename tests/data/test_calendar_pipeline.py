"""交易日历管道测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import respx
from httpx import Response

from llm_trader.data import DataStoreManager, DatasetKind, default_manager
from llm_trader.data.pipelines.calendar import TradingCalendarPipeline
from llm_trader.data.pipelines.client import EastMoneyClient
from llm_trader.data.repositories.parquet import ParquetRepository


@respx.mock
def test_calendar_pipeline_sync(tmp_path: Path) -> None:
    """应正确生成交易日历 Parquet。"""

    respx.get("https://push2.eastmoney.com/api/qt/market/getfuturestime").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "result": [
                        {"f4": "20240701", "f2": 1},
                        {"f4": "20240702", "f2": 0},
                    ]
                }
            },
        )
    )

    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    client = EastMoneyClient()
    pipeline = TradingCalendarPipeline(client=client, repository=repository)

    records = pipeline.sync(market="CN_A", start=date(2024, 7, 1), end=date(2024, 7, 2))

    client.close()
    assert len(records) == 2
    path = manager.path_for(DatasetKind.TRADING_CALENDAR)
    stored = pq.read_table(path).to_pylist()
    assert stored[0]["is_trading_day"] is True
    assert stored[1]["is_trading_day"] is False
