from __future__ import annotations

"""
数据采集与落地服务：负责将主表、实时行情、账户快照写入 PostgreSQL。
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, ContextManager, Iterable, List, Optional, Sequence, Dict

from sqlmodel import Session

from llm_trader.common import get_logger
from llm_trader.data.pipelines.realtime_quotes import RealtimeQuotesPipeline
from llm_trader.data.pipelines.symbols import SymbolsPipeline
from llm_trader.data.repositories.postgres import PostgresDataRepository
from llm_trader.db.models.enums import RiskPosture

_LOGGER = get_logger("data.ingestion.service")


SessionFactory = Callable[[], ContextManager[Session]]


@dataclass(slots=True)
class AccountPositionPayload:
    """账户持仓采集结构。"""

    symbol: str
    qty: float
    avg_price: Optional[float] = None
    market_value: Optional[float] = None


@dataclass(slots=True)
class AccountSnapshotPayload:
    """账户资金采集结构。"""

    captured_at: datetime
    nav: float
    cash: float
    available: float
    posture: RiskPosture = RiskPosture.NORMAL
    positions: Sequence[AccountPositionPayload] = ()


class DataIngestionService:
    """封装数据采集逻辑，面向新架构的 PostgreSQL 存储。"""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        symbols_pipeline: Optional[SymbolsPipeline] = None,
        quotes_pipeline: Optional[RealtimeQuotesPipeline] = None,
        symbol_universe_limit: int = 200,
    ) -> None:
        self._session_factory = session_factory
        self._symbols_pipeline = symbols_pipeline or SymbolsPipeline()
        self._quotes_pipeline = quotes_pipeline or RealtimeQuotesPipeline()
        self._symbol_universe_limit = symbol_universe_limit

    @contextmanager
    def _repository(self) -> Iterable[PostgresDataRepository]:
        with self._session_factory() as session:
            yield PostgresDataRepository(session)

    # ------------------------------------------------------------------ #
    # Master symbols
    # ------------------------------------------------------------------ #
    def sync_master_symbols(self) -> List[dict]:
        """同步证券主表到 PostgreSQL。"""
        records = self._symbols_pipeline.fetch()
        cleaned = self._normalise_symbol_records(records)
        with self._repository() as repo:
            repo.upsert_master_symbols(cleaned)
        _LOGGER.info("主表数据已写入 PostgreSQL", extra={"rows": len(cleaned)})
        return cleaned

    def _normalise_symbol_records(self, records: Sequence[dict]) -> List[dict]:
        """填充 tick/lot 等字段，避免缺失。"""
        normalised: List[dict] = []
        for record in records:
            tick_size = record.get("tick_size")
            if not tick_size:
                tick_size = 0.01
            lot_size = record.get("lot_size")
            if not lot_size:
                lot_size = 100
            as_of_date = record.get("as_of_date") or datetime.utcnow().date()
            normalised.append(
                {
                    **record,
                    "tick_size": tick_size,
                    "lot_size": lot_size,
                    "as_of_date": as_of_date,
                    "version": record.get("version", 1),
                }
            )
        return normalised

    # ------------------------------------------------------------------ #
    # Realtime quotes
    # ------------------------------------------------------------------ #
    def sync_realtime_quotes(self, symbols: Optional[Sequence[str]] = None) -> List[Dict[str, object]]:
        """同步实时行情快照。"""
        with self._repository() as repo:
            symbol_list = list(symbols or [])
            if not symbol_list:
                symbol_list = repo.list_active_symbols(limit=self._symbol_universe_limit)
                if not symbol_list:
                    self.sync_master_symbols()
                    symbol_list = repo.list_active_symbols(limit=self._symbol_universe_limit)
            if not symbol_list:
                raise RuntimeError("缺少可用标的，无法采集行情。")
            quotes = self._quotes_pipeline.fetch(symbol_list)
            repo.upsert_realtime_quotes(quotes)
        _LOGGER.info("实时行情已写入 PostgreSQL", extra={"rows": len(quotes), "symbols": len(symbol_list)})
        return quotes

    # ------------------------------------------------------------------ #
    # Account snapshot
    # ------------------------------------------------------------------ #
    def store_account_snapshot(self, payload: AccountSnapshotPayload) -> None:
        """写入账户资金与持仓快照。"""
        with self._repository() as repo:
            repo.store_account_snapshot(
                captured_at=payload.captured_at,
                nav=payload.nav,
                cash=payload.cash,
                available=payload.available,
                posture=payload.posture,
                positions=[
                    {
                        "symbol": item.symbol,
                        "qty": item.qty,
                        "avg_price": item.avg_price,
                        "market_value": item.market_value,
                    }
                    for item in payload.positions
                ],
            )
        _LOGGER.info(
            "账户快照已写入 PostgreSQL",
            extra={"captured_at": payload.captured_at.isoformat(), "positions": len(payload.positions)},
        )
