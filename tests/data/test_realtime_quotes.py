"""实时行情管道测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import pytest

from llm_trader.common import DataSourceError
from llm_trader.data import DatasetKind, default_manager
from llm_trader.config import get_settings
from llm_trader.data.pipelines.realtime_quotes import RealtimeQuotesPipeline
from llm_trader.data.repositories.parquet import ParquetRepository


class FakeClient:
    def __init__(self, payload: Dict[str, object]) -> None:
        self.payload = payload

    def get_json(self, url: str, params: Dict[str, object]) -> Dict[str, object]:
        return self.payload


def _sample_payload() -> Dict[str, object]:
    return {
        "data": {
            "diff": [
                {
                    "f12": "600000",
                    "f13": 1,
                    "f14": "浦发银行",
                    "f2": 10.5,
                    "f3": 0.12,
                    "f4": 1.15,
                    "f5": 123456,
                    "f6": 123456789.0,
                    "f7": 2.1,
                    "f8": 0.5,
                    "f9": 2.3,
                    "f10": 0.8,
                    "f15": 10.8,
                    "f16": 10.1,
                    "f17": 10.0,
                    "f18": 9.9,
                    "f128": 12.5,
                }
            ]
        }
    }


def test_realtime_quotes_pipeline_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    get_settings.cache_clear()
    repository = ParquetRepository()
    pipeline = RealtimeQuotesPipeline(client=FakeClient(_sample_payload()), repository=repository)

    records = pipeline.sync(["600000.SH"])
    assert len(records) == 1
    assert records[0]["symbol"] == "600000.SH"
    manager = default_manager()
    path = manager.path_for(
        DatasetKind.REALTIME_QUOTES,
        symbol="600000.SH",
        timestamp=records[0]["snapshot_time"],
    )
    assert path.exists()
    df = pd.read_parquet(path)
    assert df.iloc[0]["last_price"] == records[0]["last_price"]


def test_realtime_quotes_pipeline_sync_uses_symbol_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    get_settings.cache_clear()
    repository = ParquetRepository()
    repository.write_symbols(
        [
            {
                "symbol": "600000.SH",
                "name": "浦发银行",
                "board": "主板",
                "listed_date": datetime(1999, 11, 10),
                "delisted_date": None,
                "status": "active",
                "exchange": "SH",
                "industry": "银行",
            },
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "board": "主板",
                "listed_date": datetime(1991, 4, 3),
                "delisted_date": None,
                "status": "active",
                "exchange": "SZ",
                "industry": "银行",
            },
        ]
    )

    class RecordingClient:
        def __init__(self) -> None:
            self.requests: List[str] = []

        def get_json(self, url: str, params: Dict[str, object]) -> Dict[str, object]:
            self.requests.append(str(params.get("secids", "")))
            return {
                "data": {
                    "diff": [
                        {
                            "f12": "600000",
                            "f13": 1,
                            "f14": "浦发银行",
                            "f2": 10.5,
                        },
                        {
                            "f12": "000001",
                            "f13": 0,
                            "f14": "平安银行",
                            "f2": 12.3,
                        },
                    ]
                }
            }

    client = RecordingClient()
    pipeline = RealtimeQuotesPipeline(client=client, repository=repository)
    records = pipeline.sync()
    symbols = {record["symbol"] for record in records}
    assert symbols == {"600000.SH", "000001.SZ"}
    assert client.requests  # 确认已发起请求


def test_realtime_quotes_pipeline_requires_symbols(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    get_settings.cache_clear()
    pipeline = RealtimeQuotesPipeline(client=FakeClient({"data": {"diff": []}}))
    with pytest.raises(DataSourceError):
        pipeline.sync()
