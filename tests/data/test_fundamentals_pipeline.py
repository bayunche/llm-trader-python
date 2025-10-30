"""基础指标管道测试。"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import respx
from httpx import Response

from llm_trader.data import DatasetKind, default_manager
from llm_trader.data.pipelines.client import EastMoneyClient
from llm_trader.data.pipelines.fundamentals import FundamentalsPipeline
from llm_trader.data.repositories.parquet import ParquetRepository


@respx.mock
def test_fundamentals_pipeline_sync(tmp_path: Path) -> None:
    """应正确写入基础指标数据。"""

    base_url = "https://push2.eastmoney.com/api/qt/stock/get"
    respx.get(base_url).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "f57": "20240701",
                    "f162": "12.5",
                    "f164": "1.8",
                    "f116": "35000000000",
                    "f117": "32000000000",
                    "f167": "2.1",
                    "f168": "45.0",
                    "f169": "18.0",
                }
            },
        )
    )

    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    client = EastMoneyClient()
    pipeline = FundamentalsPipeline(client=client, repository=repository)

    records = pipeline.sync(["600000.SH"])

    client.close()
    assert len(records) == 1
    from datetime import datetime

    path = manager.path_for(
        DatasetKind.FUNDAMENTALS,
        symbol="600000.SH",
        timestamp=datetime(2024, 1, 1),
    )
    stored = pq.read_table(path).to_pylist()
    assert stored[0]["symbol"] == "600000.SH"
    assert float(stored[0]["pe"]) == 12.5
