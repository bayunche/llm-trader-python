"""证券主表管道测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import json

import pyarrow.parquet as pq
import respx
from httpx import Response

from llm_trader.data import DatasetKind, default_manager
from llm_trader.data.pipelines.client import EastMoneyClient
from llm_trader.data.pipelines.symbols import SymbolsPipeline
from llm_trader.data.repositories.parquet import ParquetRepository


@respx.mock
def test_symbols_pipeline_sync(tmp_path: Path) -> None:
    """应正确下载并写入证券主表数据。"""

    primary_route = respx.get("https://push2.eastmoney.com/api/qt/clist/get").mock(
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
    assert primary_route.called
    assert len(records) == 1
    output_path = manager.path_for(DatasetKind.SYMBOLS)
    stored = pq.read_table(output_path).to_pylist()
    assert stored[0]["symbol"] == "600000.SH"
    assert stored[0]["name"] == "浦发银行"


@respx.mock
def test_symbols_pipeline_endpoint_fallback(tmp_path: Path) -> None:
    """当东方财富接口全部失败时，自动切换至交易所数据源。"""

    respx.get("https://push2.eastmoney.com/api/qt/clist/get").mock(
        return_value=Response(502, json={}),
    )
    respx.get("https://80.push2.eastmoney.com/api/qt/clist/get").mock(
        return_value=Response(502, json={}),
    )
    respx.get("https://81.push2.eastmoney.com/api/qt/clist/get").mock(
        return_value=Response(502, json={}),
    )
    respx.get("https://82.push2.eastmoney.com/api/qt/clist/get").mock(
        return_value=Response(502, json={}),
    )
    respx.get("https://83.push2.eastmoney.com/api/qt/clist/get").mock(
        return_value=Response(502, json={}),
    )

    sse_route = respx.get("https://query.sse.com.cn/security/stock/getStockListData2.do").mock(
        return_value=Response(
            200,
            content=json.dumps(
                {
                    "result": [
                        {
                            "SECURITY_CODE_A": "600000",
                            "SECURITY_ABBR_A": "浦发银行",
                            "BOARD_NAME": "上海主板",
                            "LISTING_DATE_A": "19991110",
                        }
                    ]
                }
            ).encode("utf-8"),
        )
    )
    szse_route = respx.get("https://www.szse.cn/api/report/ShowReport/data").mock(
        return_value=Response(
            200,
            json=[
                {
                    "data": [
                        {
                            "zqdm": "000001",
                            "zqmc": "平安银行",
                            "zqlb": "深圳主板",
                            "ssrq": "19910403",
                        }
                    ]
                }
            ],
        )
    )

    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    client = EastMoneyClient()
    pipeline = SymbolsPipeline(client=client, repository=repository, page_size=100)

    records = pipeline.sync()

    client.close()
    assert sse_route.called
    assert szse_route.called
    symbols = {item["symbol"] for item in records}
    assert {"600000.SH", "000001.SZ"} <= symbols


@respx.mock
def test_symbols_pipeline_cache_fallback(tmp_path: Path) -> None:
    """当所有线上接口不可用时，应读取缓存的证券主表。"""

    # 东方财富所有端点均失败
    for host in [
        "https://push2.eastmoney.com/api/qt/clist/get",
        "https://80.push2.eastmoney.com/api/qt/clist/get",
        "https://81.push2.eastmoney.com/api/qt/clist/get",
        "https://82.push2.eastmoney.com/api/qt/clist/get",
        "https://83.push2.eastmoney.com/api/qt/clist/get",
    ]:
        respx.get(host).mock(return_value=Response(502, json={}))

    # 交易所接口返回 500，触发降级
    sse_route = respx.get("https://query.sse.com.cn/security/stock/getStockListData2.do").mock(
        return_value=Response(500, text="error"),
    )
    szse_route = respx.get("https://www.szse.cn/api/report/ShowReport/data").mock(
        return_value=Response(500, json={}),
    )

    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    repository.write_symbols(
        [
            {
                "symbol": "600001.SH",
                "name": "示例股份",
                "board": "上海主板",
                "listed_date": date(2020, 1, 1),
                "status": "active",
                "exchange": "SH",
            }
        ]
    )

    client = EastMoneyClient()
    pipeline = SymbolsPipeline(client=client, repository=repository, page_size=100)

    records = pipeline.fetch()

    client.close()
    assert sse_route.called
    assert szse_route.called
    assert len(records) == 1
    assert records[0]["symbol"] == "600001.SH"
    assert records[0]["name"] == "示例股份"
