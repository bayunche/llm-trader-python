"""基础指标采集管道。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

from llm_trader.common import DataSourceError, get_logger
from llm_trader.data.quality import drop_duplicates, drop_na, ensure_columns, sort_records
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.data.utils import parse_date, to_secid

from .client import EastMoneyClient


_FUNDAMENTALS_URL = "https://push2.eastmoney.com/api/qt/stock/get"
_LOGGER = get_logger("data.pipeline.fundamentals")


class FundamentalsPipeline:
    """东方财富基础指标同步。"""

    def __init__(
        self,
        *,
        client: Optional[EastMoneyClient] = None,
        repository: Optional[ParquetRepository] = None,
    ) -> None:
        self.client = client or EastMoneyClient()
        self.repository = repository or ParquetRepository()

    def fetch(self, symbols: Iterable[str]) -> List[Dict[str, object]]:
        records: List[Dict[str, object]] = []
        for symbol in symbols:
            params = {
                "secid": to_secid(symbol),
                "fields": "f58,f116,f117,f162,f164,f167,f168,f169,f57",
            }
            payload = self.client.get_json(_FUNDAMENTALS_URL, params=params)
            data = payload.get("data")
            if not data:
                _LOGGER.warning("基础指标数据为空", extra={"symbol": symbol})
                continue
            record = self._parse_record(symbol, data)
            if record:
                records.append(record)

        if not records:
            raise DataSourceError("未获取到任何基础指标数据")

        ensure_columns(records, ["symbol", "date"])
        cleaned = drop_duplicates(records, subset=["symbol", "date"])
        cleaned = drop_na(cleaned, subset=["symbol", "date"])
        cleaned = sort_records(cleaned, "date")
        return cleaned

    def sync(self, symbols: Iterable[str]) -> List[Dict[str, object]]:
        records = self.fetch(symbols)
        self.repository.write_fundamentals(records)
        _LOGGER.info("基础指标同步完成", extra={"rows": len(records)})
        return records

    @staticmethod
    def _parse_record(symbol: str, data: Dict[str, object]) -> Optional[Dict[str, object]]:
        trade_date = data.get("f57") or data.get("f60")
        parsed = parse_date(str(trade_date)) if trade_date else None
        record_date = parsed.date() if parsed else date.today()

        def _to_float(value: object) -> Optional[float]:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return {
            "symbol": symbol,
            "date": record_date,
            "pe": _to_float(data.get("f162")),
            "pb": _to_float(data.get("f164")),
            "mkt_cap": _to_float(data.get("f116")),
            "float_mkt_cap": _to_float(data.get("f117")),
            "turnover": _to_float(data.get("f167")),
            "gross_profit_margin": _to_float(data.get("f168")),
            "net_profit_margin": _to_float(data.get("f169")),
        }


__all__ = ["FundamentalsPipeline"]
