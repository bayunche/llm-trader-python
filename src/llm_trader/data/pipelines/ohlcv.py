"""K 线数据采集管道。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from llm_trader.common import DataSourceError, ValidationError, get_logger
from llm_trader.data.quality import (
    assert_sorted,
    drop_duplicates,
    drop_na,
    ensure_columns,
    sort_records,
)
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.data.utils import parse_datetime, to_secid

from .client import EastMoneyClient


_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_LOGGER = get_logger("data.pipeline.ohlcv")

_FREQ_MAPPING = {
    "d": 101,  # 日线
    "w": 102,
    "m": 103,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
    "1m": 1,
}


class OhlcvPipeline:
    """东方财富 K 线数据采集与落地。"""

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
        symbol: str,
        freq: str = "D",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[Dict[str, object]]:
        freq_key = freq.lower()
        if freq_key not in _FREQ_MAPPING:
            raise ValidationError(f"不支持的频率：{freq}")
        params = {
            "secid": to_secid(symbol),
            "klt": _FREQ_MAPPING[freq_key],
            "fqt": 1,
            "lmt": 0,
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        }
        if start:
            params["beg"] = start.strftime("%Y%m%d")
        else:
            params["beg"] = 0
        if end:
            params["end"] = end.strftime("%Y%m%d")
        else:
            params["end"] = 20500000

        payload = self.client.get_json(_KLINE_URL, params=params)
        data = payload.get("data")
        if not data:
            raise DataSourceError("东方财富未返回行情数据")
        klines = data.get("klines") or []
        records: List[Dict[str, object]] = []
        for line in klines:
            parsed = self._parse_kline_line(line, symbol, freq.upper())
            if parsed:
                records.append(parsed)

        if not records:
            return []

        freq_label = freq.upper() if freq_key in {"d", "w", "m"} else freq_key
        for record in records:
            record["freq"] = freq_label

        ensure_columns(records, ["dt", "symbol", "freq", "open", "high", "low", "close"])
        cleaned = drop_na(records, ["dt", "symbol"])
        cleaned = drop_duplicates(cleaned, ["symbol", "dt", "freq"])
        cleaned = sort_records(cleaned, "dt")
        assert_sorted(cleaned, "dt")
        return cleaned

    def sync(
        self,
        symbol: str,
        freq: str = "D",
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[Dict[str, object]]:
        freq_key = freq.lower()
        if freq_key not in _FREQ_MAPPING:
            raise ValidationError(f"不支持的频率：{freq}")
        freq_label = freq.upper() if freq_key in {"d", "w", "m"} else freq_key
        if start is None:
            latest = self.repository.latest_timestamp(symbol, freq_label)
            if latest is not None:
                start = (latest + timedelta(seconds=1)).date()
        records = self.fetch(symbol=symbol, freq=freq_label, start=start, end=end)
        if not records:
            _LOGGER.info("未获取到行情数据", extra={"symbol": symbol, "freq": freq})
            return []
        self.repository.write_ohlcv(records, freq=freq_label)
        _LOGGER.info(
            "行情同步完成",
            extra={"symbol": symbol, "freq": freq_label, "rows": len(records)},
        )
        return records

    @staticmethod
    def _parse_kline_line(line: str, symbol: str, freq: str) -> Optional[Dict[str, object]]:
        parts = line.split(",")
        if len(parts) < 7:
            return None
        dt = parse_datetime(parts[0])
        if not dt:
            return None
        open_price = float(parts[1])
        close_price = float(parts[2])
        high_price = float(parts[3])
        low_price = float(parts[4])
        volume = float(parts[5])
        amount = float(parts[6])
        turnover = float(parts[9]) if len(parts) > 9 and parts[9] else None
        suspended = close_price == 0 and high_price == 0 and low_price == 0
        return {
            "symbol": symbol,
            "dt": dt,
            "freq": freq,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "amount": amount,
            "turnover_rate": turnover,
            "adj_factor": None,
            "suspended": suspended,
        }


__all__ = ["OhlcvPipeline"]
