"""证券主表采集管道。"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

import httpx

from llm_trader.common import DataSourceError, get_logger
from llm_trader.data.quality import drop_duplicates, drop_na, ensure_columns, sort_records
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.data.utils import build_symbol, parse_date

from .client import EastMoneyClient


_SYMBOLS_ENDPOINTS = [
    "https://push2.eastmoney.com/api/qt/clist/get",
    "https://80.push2.eastmoney.com/api/qt/clist/get",
    "https://81.push2.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://83.push2.eastmoney.com/api/qt/clist/get",
]
_SSE_URL = "https://query.sse.com.cn/security/stock/getStockListData2.do"
_SZSE_URL = "https://www.szse.cn/api/report/ShowReport"
_SZSE_TABS = ("tab1", "tab2", "tab3")
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
        last_error: Optional[Exception] = None
        for endpoint in _SYMBOLS_ENDPOINTS:
            try:
                return self._fetch_from_endpoint(endpoint)
            except Exception as exc:  # pragma: no cover - 网络异常按降级策略处理
                last_error = exc
                _LOGGER.warning("证券主表接口访问失败，尝试备用端点", extra={"endpoint": endpoint, "error": str(exc)})
        try:
            return self._fetch_from_exchanges()
        except Exception as exc:
            if last_error:
                raise DataSourceError("东方财富未返回任何证券数据") from exc
            raise DataSourceError("东方财富未返回任何证券数据") from exc

    def _fetch_from_endpoint(self, endpoint: str) -> List[Dict[str, object]]:
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
            payload = self.client.get_json(endpoint, params=params)
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

    def _fetch_from_exchanges(self) -> List[Dict[str, object]]:
        records: List[Dict[str, object]] = []
        records.extend(self._fetch_sse())
        records.extend(self._fetch_szse())
        if not records:
            raise DataSourceError("上交所/深交所接口未返回证券数据")
        ensure_columns(records, ["symbol", "name"])
        cleaned = drop_duplicates(records, subset=["symbol"])
        cleaned = sort_records(cleaned, "symbol")
        return cleaned

    def _fetch_sse(self) -> List[Dict[str, object]]:
        headers = {
            "Referer": "http://www.sse.com.cn/assortment/stock/list/share/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        }
        params = {
            "isPagination": "true",
            "stockType": "1",
            "pageHelp.pageSize": "2000",
            "pageHelp.pageNo": "1",
            "pageHelp.beginPage": "1",
            "pageHelp.endPage": "1",
        }
        with httpx.Client(headers=headers, timeout=10.0) as client:
            response = client.get(_SSE_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        items = payload.get("result", [])
        records: List[Dict[str, object]] = []
        for item in items:
            code = item.get("SECURITY_CODE_A") or item.get("SECURITY_CODE_B")
            name = item.get("SECURITY_ABBR_A") or item.get("SECURITY_ABBR_B")
            if not code or not name:
                continue
            listed_date = parse_date(item.get("LISTING_DATE_A") or item.get("LISTING_DATE_B"))
            board = item.get("BOARD_NAME") or item.get("BOARD_NAME_B") or "上海主板"
            records.append(
                {
                    "symbol": f"{code}.SH",
                    "name": str(name),
                    "board": str(board),
                    "listed_date": listed_date.date() if listed_date else None,
                    "status": "active",
                    "exchange": "SH",
                }
            )
        return records

    def _fetch_szse(self) -> List[Dict[str, object]]:
        headers = {
            "Referer": "http://www.szse.cn/market/stock/list/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        }
        records: List[Dict[str, object]] = []
        with httpx.Client(headers=headers, timeout=10.0) as client:
            for tab in _SZSE_TABS:
                params = {
                    "SHOWTYPE": "JSON",
                    "CATALOGID": "1110",
                    "TABKEY": tab,
                    "random": f"0.{random.randint(100000, 999999)}",
                }
                response = client.get(_SZSE_URL, params=params)
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data", [])
                for item in data:
                    code = item.get("zqdm")
                    name = item.get("zqmc")
                    if not code or not name:
                        continue
                    listed_date = parse_date(item.get("ssrq"))
                    board = item.get("zqlb") or "深圳市场"
                    records.append(
                        {
                            "symbol": f"{code}.SZ",
                            "name": str(name),
                            "board": str(board),
                            "listed_date": listed_date.date() if listed_date else None,
                            "status": "active",
                            "exchange": "SZ",
                        }
                    )
        return records

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
