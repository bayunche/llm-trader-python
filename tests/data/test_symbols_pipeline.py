"""证券主表管道测试。"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import respx
from httpx import Response

from llm_trader.data import DataStoreManager, DatasetKind, default_manager
from llm_trader.data.pipelines.client import EastMoneyClient
from llm_trader.data.pipelines.symbols import SymbolsPipeline
from llm_trader.data.repositories.parquet import ParquetRepository


@respx.mock
def test_symbols_pipeline_sync(tmp_path: Path) -> None:
    """应正确下载并写入证券主表数据。"""

    route = respx.get("https://80.push2.eastmoney.com/api/qt/clist/get").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "total": 1,
                    "diff": [
                        {
                            "f12": "600000",
                            "f13": "SH",
                            "f14": "浦发银行",
                            "f100": "主板",
                            "f26": "19991210",
                            "f104": "",
                            "f128": "银行",
                            "f184": 1,
                        }
                    ],
                }
            },
        )
    )

    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    client = EastMoneyClient()
    pipeline = SymbolsPipeline(client=client, repository=repository, page_size=100)

    records = pipeline.sync()

    client.close()
    assert route.called
    assert len(records) == 1
    output_path = manager.path_for(DatasetKind.SYMBOLS)
    stored = pq.read_table(output_path).to_pylist()
    assert stored[0]["symbol"] == "600000.SH"
    assert stored[0]["name"] == "浦发银行"
