"""证券主表采集管道。"""

from __future__ import annotations

from typing import Dict, List, Optional

from llm_trader.common import DataSourceError, get_logger
from llm_trader.data.quality import drop_duplicates, drop_na, ensure_columns, sort_records
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.data.utils import build_symbol, parse_date

from .client import EastMoneyClient


_SYMBOLS_URL = "https://80.push2.eastmoney.com/api/qt/clist/get"
_LOGGER = get_logger("data.pipeline.symbols")


class SymbolsPipeline:
    """东方财富证券主表采集与落地。"""

    def __init__(
        self,
        *,
        client: Optional[EastMoneyClient] = None,
        repository: Optional[ParquetRepository] = None,
        page_size: int = 2000,
    ) -> None:
        self.client = client or EastMoneyClient()
        self.repository = repository or ParquetRepository()
        self.page_size = page_size

    def fetch(self) -> List[Dict[str, object]]:
        records: List[Dict[str, object]] = []
        page = 1
        total = None

        while True:
            params = {
                "pn": page,
                "pz": self.page_size,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                "fields": "f12,f13,f14,f100,f101,f128,f136,f184,f204,f21,f26,f104,f184",
            }
            payload = self.client.get_json(_SYMBOLS_URL, params=params)
            data = payload.get("data")
            if not data:
                break
            total = data.get("total") or total
            diff = data.get("diff") or []
            if not diff:
                break
            for item in diff:
                parsed = self._parse_symbol(item)
                if parsed:
                    records.append(parsed)
            if total is not None and page * self.page_size >= int(total):
                break
            page += 1

        if not records:
            raise DataSourceError("东方财富未返回任何证券数据")

        ensure_columns(records, ["symbol", "name", "board", "listed_date", "status"])
        cleaned = drop_duplicates(records, subset=["symbol"])
        cleaned = drop_na(cleaned, subset=["symbol", "name"])
        cleaned = sort_records(cleaned, "symbol")
        return cleaned

    def sync(self) -> List[Dict[str, object]]:
        records = self.fetch()
        self.repository.write_symbols(records)
        _LOGGER.info("证券主表同步完成", extra={"rows": len(records)})
        return records

    @staticmethod
    def _parse_symbol(item: Dict[str, object]) -> Optional[Dict[str, object]]:
        code = item.get("f12")
        exchange = item.get("f13")
        name = item.get("f14")
        if not code or not exchange:
            return None
        symbol = build_symbol(str(code), str(exchange))
        board_raw = item.get("f100")
        board = str(board_raw).strip() if board_raw else "未知"
        listed_date = parse_date(str(item.get("f26")) if item.get("f26") else None)
        delisted_date = parse_date(str(item.get("f104")) if item.get("f104") else None)
        industry = str(item.get("f128") or "") or None
        status_flag = item.get("f184") or 1
        if isinstance(status_flag, str) and status_flag.isdigit():
            status_flag = int(status_flag)
        status = "active" if status_flag in (1, "1", None) else "suspended"
        exchange_code = str(exchange).upper()
        return {
            "symbol": symbol,
            "name": str(name),
            "board": board,
            "listed_date": listed_date.date() if listed_date else None,
            "delisted_date": delisted_date.date() if delisted_date else None,
            "status": status,
            "exchange": exchange_code,
            "industry": industry,
        }


__all__ = ["SymbolsPipeline"]
