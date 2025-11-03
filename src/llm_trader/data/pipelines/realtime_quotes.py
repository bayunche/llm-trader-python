"""实时行情采集管道。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from llm_trader.common import DataSourceError, get_logger
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.data.pipelines.symbols import SymbolsPipeline
from .client import EastMoneyClient


_QUOTES_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"
_LOGGER = get_logger("data.pipeline.realtime")


class RealtimeQuotesPipeline:
    """东方财富最新行情快照。"""

    def __init__(
        self,
        *,
        client: Optional[EastMoneyClient] = None,
        repository: Optional[ParquetRepository] = None,
        symbols_limit: Optional[int] = None,
    ) -> None:
        self.client = client or EastMoneyClient()
        self.repository = repository or ParquetRepository()
        self.symbols_limit = symbols_limit

    def fetch(self, symbols: Iterable[str]) -> List[Dict[str, object]]:
        symbol_list = list(symbols)
        if not symbol_list:
            return []

        records: List[Dict[str, object]] = []
        # 东方财富一次最多支持 60+ 证券，按 50 分组稳妥
        chunk_size = 50
        for i in range(0, len(symbol_list), chunk_size):
            chunk = symbol_list[i : i + chunk_size]
            secids = ",".join(self._to_secid(symbol) for symbol in chunk)
            params = {
                "fltt": "2",
                "secids": secids,
                "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f15,f16,f17,f18,f20,f21,f13,f22,f23,f24,f25,f45,f128",
            }
            payload = self.client.get_json(_QUOTES_URL, params=params)
            data = payload.get("data")
            if not data:
                continue
            diff = data.get("diff") or []
            for item in diff:
                parsed = self._parse_quote(item)
                if parsed:
                    records.append(parsed)

        if not records:
            raise DataSourceError("未获取到实时行情")
        return records

    def sync(self, symbols: Optional[Sequence[str]] = None) -> List[Dict[str, object]]:
        symbol_list = list(symbols or [])
        if not symbol_list:
            symbol_list = self.repository.list_active_symbols(limit=self.symbols_limit)
        if not symbol_list:
            SymbolsPipeline(repository=self.repository).sync()
            symbol_list = self.repository.list_active_symbols(limit=self.symbols_limit)
        if not symbol_list:
            raise DataSourceError("缺少可用标的，请先同步证券主表或提供候选列表")

        records = self.fetch(symbol_list)
        snapshot_time = datetime.utcnow()
        for record in records:
            record.setdefault("snapshot_time", snapshot_time)
        self.repository.write_realtime_quotes(records)
        _LOGGER.info("实时行情同步完成", extra={"quotes": len(records), "symbols": symbol_list})
        return records

    @staticmethod
    def _to_secid(symbol: str) -> str:
        if symbol.endswith(".SH"):
            return f"1.{symbol[:-3]}"
        if symbol.endswith(".SZ"):
            return f"0.{symbol[:-3]}"
        if symbol.endswith(".BJ"):
            return f"0.{symbol[:-3]}"
        return symbol

    @staticmethod
    def _parse_quote(item: Dict[str, object]) -> Optional[Dict[str, object]]:
        symbol_code = item.get("f12")
        exchange = item.get("f13")
        name = item.get("f14")
        if not symbol_code:
            return None
        if exchange is None or str(exchange) == "":
            return None
        normalized_exchange = RealtimeQuotesPipeline._normalize_exchange(exchange)
        if not normalized_exchange:
            return None
        symbol = f"{symbol_code}.{normalized_exchange}"
        price = item.get("f2")
        change = item.get("f3")
        change_ratio = item.get("f4")
        volume = item.get("f5")
        amount = item.get("f6")
        high = item.get("f15")
        low = item.get("f16")
        open_price = item.get("f17")
        prev_close = item.get("f18")
        turnover_rate = item.get("f10")
        amplitude = item.get("f7")
        pe = item.get("f128")
        return {
            "symbol": symbol,
            "name": name,
            "last_price": price,
            "change": change,
            "change_ratio": change_ratio,
            "volume": volume,
            "amount": amount,
            "high": high,
            "low": low,
            "open": open_price,
            "prev_close": prev_close,
            "turnover_rate": turnover_rate,
            "amplitude": amplitude,
            "pe": pe,
            "snapshot_time": datetime.utcnow(),
        }

    @staticmethod
    def _normalize_exchange(value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        mapping = {
            "1": "SH",
            "0": "SZ",
            "2": "BJ",
            "3": "HK",
        }
        return mapping.get(text, text.upper())


__all__ = ["RealtimeQuotesPipeline"]
