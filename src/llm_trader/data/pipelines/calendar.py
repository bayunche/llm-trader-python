"""交易日历采集管道。"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from llm_trader.common import DataSourceError, get_logger
from llm_trader.data.quality import drop_duplicates, ensure_columns, sort_records
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.data.utils import parse_date

from .client import EastMoneyClient


_CALENDAR_URL = "https://push2.eastmoney.com/api/qt/market/getfuturestime"
_LOGGER = get_logger("data.pipeline.calendar")


class TradingCalendarPipeline:
    """东方财富交易日历同步。"""

    def __init__(
        self,
        *,
        client: Optional[EastMoneyClient] = None,
        repository: Optional[ParquetRepository] = None,
    ) -> None:
        self.client = client or EastMoneyClient()
        self.repository = repository or ParquetRepository()

    def fetch(
        self,
        market: str = "CN_A",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[Dict[str, object]]:
        params = {
            "fields": "f1,f2,f4",
            "market": market,
        }
        if start:
            params["beg"] = start.strftime("%Y%m%d")
        if end:
            params["end"] = end.strftime("%Y%m%d")

        payload = self.client.get_json(_CALENDAR_URL, params=params)
        data = payload.get("data")
        if not data:
            raise DataSourceError("东方财富未返回交易日历数据")
        items = data.get("result") or data.get("tradedata") or []
        records: List[Dict[str, object]] = []
        for item in items:
            entry = self._parse_calendar_item(item, market)
            if entry:
                records.append(entry)

        if not records:
            raise DataSourceError("交易日历数据为空")

        ensure_columns(records, ["date", "market", "is_trading_day"])
        cleaned = drop_duplicates(records, subset=["date", "market"])
        cleaned = sort_records(cleaned, "date")
        return cleaned

    def sync(
        self,
        market: str = "CN_A",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[Dict[str, object]]:
        records = self.fetch(market=market, start=start, end=end)
        self.repository.write_trading_calendar(records)
        _LOGGER.info("交易日历同步完成", extra={"rows": len(records)})
        return records

    @staticmethod
    def _parse_calendar_item(item: Dict[str, object], market: str) -> Optional[Dict[str, object]]:
        raw_date = item.get("f4") or item.get("date")
        parsed = parse_date(str(raw_date) if raw_date else None)
        if not parsed:
            return None
        is_open = item.get("f2") or item.get("isOpen") or item.get("is_open")
        if isinstance(is_open, str) and is_open.isdigit():
            is_open = int(is_open)
        is_trading_day = bool(is_open)
        return {
            "date": parsed.date(),
            "market": market,
            "is_trading_day": is_trading_day,
        }


__all__ = ["TradingCalendarPipeline"]
