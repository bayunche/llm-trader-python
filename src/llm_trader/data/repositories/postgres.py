from __future__ import annotations

"""
基于 PostgreSQL 的数据仓储实现，负责主表、行情、账户快照等存取。
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select
from sqlmodel import Session

from llm_trader.db.models import (
    AccountPosition,
    AccountSnapshot,
    MasterSymbol,
    RealtimeQuote,
)
from llm_trader.db.models.enums import RiskPosture


class PostgresDataRepository:
    """封装对 SQLModel Session 的数据访问。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- Master Symbols -------------------------------------------------
    def upsert_master_symbols(self, records: Sequence[Dict[str, object]]) -> int:
        """写入证券主表，存在时覆盖。"""
        affected = 0
        for record in records:
            symbol = str(record["symbol"])
            instance = MasterSymbol(
                symbol=symbol,
                exchange=str(record.get("exchange") or "") or "UNKNOWN",
                board=str(record.get("board") or "") or "未知",
                name=str(record.get("name") or symbol),
                is_st=bool(record.get("is_st", False)),
                list_date=record.get("listed_date"),
                industry=record.get("industry"),
                market_cap=record.get("market_cap"),
                float_cap=record.get("float_cap"),
                pe_ttm=record.get("pe_ttm"),
                pb=record.get("pb"),
                tick_size=float(record.get("tick_size", 0.01) or 0.01),
                lot_size=int(record.get("lot_size", 100) or 100),
                trading_status=str(record.get("status") or "active"),
                as_of_date=record.get("as_of_date"),
                version=int(record.get("version") or 1),
            )
            self.session.merge(instance)
            affected += 1
        return affected

    def list_active_symbols(self, *, limit: Optional[int] = None) -> List[str]:
        """返回活跃证券列表。"""
        statement = (
            select(MasterSymbol.symbol)
            .where(MasterSymbol.trading_status.in_(["active", "suspended"]))
            .order_by(MasterSymbol.symbol)
        )
        if limit:
            statement = statement.limit(limit)
        rows = self.session.exec(statement).all()
        return list(dict.fromkeys(rows))

    def get_master_symbol_map(self, symbols: Iterable[str]) -> Dict[str, MasterSymbol]:
        """获取指定标的的主表信息映射。"""
        symbol_list = list(symbols)
        if not symbol_list:
            return {}
        rows = self.session.exec(
            select(MasterSymbol).where(MasterSymbol.symbol.in_(symbol_list))
        ).all()
        return {row.symbol: row for row in rows}

    # -- Realtime Quotes ------------------------------------------------
    def upsert_realtime_quotes(self, records: Sequence[Dict[str, object]]) -> int:
        """写入实时行情。"""
        affected = 0
        for record in records:
            symbol = str(record["symbol"])
            snapshot_time = record.get("snapshot_time") or datetime.utcnow()
            quote = RealtimeQuote(
                symbol=symbol,
                name=record.get("name"),
                last_price=self._safe_float(record.get("last_price")),
                change=self._safe_float(record.get("change")),
                change_ratio=self._safe_float(record.get("change_ratio")),
                volume=self._safe_float(record.get("volume")),
                amount=self._safe_float(record.get("amount")),
                high=self._safe_float(record.get("high")),
                low=self._safe_float(record.get("low")),
                open=self._safe_float(record.get("open")),
                prev_close=self._safe_float(record.get("prev_close")),
                turnover_rate=self._safe_float(record.get("turnover_rate")),
                amplitude=self._safe_float(record.get("amplitude")),
                pe=self._safe_float(record.get("pe")),
                snapshot_time=snapshot_time,
            )
            self.session.merge(quote)
            affected += 1
        return affected

    def get_latest_quotes(self, symbols: Iterable[str]) -> Dict[str, RealtimeQuote]:
        """返回指定标的的最新行情。"""
        symbol_list = list(symbols)
        if not symbol_list:
            return {}
        rows = self.session.exec(
            select(RealtimeQuote).where(RealtimeQuote.symbol.in_(symbol_list))
        ).all()
        return {row.symbol: row for row in rows}

    # -- Account Snapshot ----------------------------------------------
    def store_account_snapshot(
        self,
        *,
        captured_at: datetime,
        nav: float,
        cash: float,
        available: float,
        posture: RiskPosture,
        positions: Sequence[Dict[str, object]],
    ) -> None:
        """保存账户资金与持仓快照。"""
        snapshot = AccountSnapshot(
            captured_at=captured_at,
            nav=nav,
            cash=cash,
            available=available,
            risk_posture=posture,
        )
        self.session.add(snapshot)

        existing_positions = self.session.exec(
            select(AccountPosition).where(AccountPosition.captured_at == captured_at)
        ).all()
        for row in existing_positions:
            self.session.delete(row)

        for record in positions:
            position = AccountPosition(
                captured_at=captured_at,
                symbol=str(record["symbol"]),
                qty=float(record.get("qty", 0.0)),
                avg_price=self._safe_float(record.get("avg_price")),
                market_value=self._safe_float(record.get("market_value")),
            )
            self.session.add(position)

    def latest_account_snapshot(self) -> Optional[AccountSnapshot]:
        """获取最新账户资金快照。"""
        return self.session.exec(
            select(AccountSnapshot).order_by(AccountSnapshot.captured_at.desc()).limit(1)
        ).first()

    def latest_positions(self) -> Dict[str, AccountPosition]:
        """获取最新一次快照的持仓列表。"""
        latest_snapshot = self.latest_account_snapshot()
        if not latest_snapshot:
            return {}
        rows = self.session.exec(
            select(AccountPosition).where(AccountPosition.captured_at == latest_snapshot.captured_at)
        ).all()
        return {row.symbol: row for row in rows}

    # -- Utilities -----------------------------------------------------
    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def to_position_payload(self) -> List[Dict[str, object]]:
        """返回最新持仓的序列化结果，主要给观测构建使用。"""
        positions = self.latest_positions()
        latest_quote_map = self.get_latest_quotes(positions.keys())
        payload: List[Dict[str, object]] = []
        for symbol, position in positions.items():
            quote = latest_quote_map.get(symbol)
            payload.append(
                {
                    "symbol": symbol,
                    "qty": position.qty,
                    "avg_price": position.avg_price,
                    "market_value": position.market_value,
                    "last_price": quote.last_price if quote else None,
                }
            )
        return payload

    def to_universe_features(
        self,
        *,
        symbols: Sequence[str],
        include_quotes: bool = True,
    ) -> Dict[str, Dict[str, object]]:
        """根据标的列表构建观测特征。"""
        universe = list(dict.fromkeys(symbols))
        if not universe:
            return {}
        master_map = self.get_master_symbol_map(universe)
        quotes_map = self.get_latest_quotes(universe) if include_quotes else {}
        features: Dict[str, Dict[str, object]] = {}
        for symbol in universe:
            master = master_map.get(symbol)
            quote = quotes_map.get(symbol)
            if not master:
                continue
            last_price = quote.last_price if quote else None
            prev_close = quote.prev_close if quote else None
            change_ratio = quote.change_ratio if quote else None
            ret_5m = None
            if change_ratio is not None:
                ret_5m = change_ratio / 100.0
            features[symbol] = {
                "last": last_price,
                "prev_close": prev_close,
                "ret_5m": ret_5m,
                "volume": quote.volume if quote else None,
                "turnover": quote.amount if quote else None,
                "turnover_rate": quote.turnover_rate if quote else None,
                "risk_flags": self._build_risk_flags(master),
            }
        return features

    @staticmethod
    def _build_risk_flags(master: MasterSymbol) -> List[str]:
        flags: List[str] = []
        if master.trading_status and master.trading_status.lower() != "active":
            flags.append(master.trading_status.lower())
        if master.is_st:
            flags.append("st")
        return flags
