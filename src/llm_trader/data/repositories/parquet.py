"""Parquet 数据仓储实现。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

from llm_trader.common import get_logger
from llm_trader.data import DataStoreManager, DatasetConfig, DatasetKind, default_manager
from llm_trader.data.quality import drop_duplicates, drop_na

Record = Dict[str, Any]

_LOGGER = get_logger("data.repo.parquet")


@dataclass
class ParquetRepository:
    """负责将数据写入 Parquet 并处理增量逻辑。"""

    manager: DataStoreManager = field(default_factory=default_manager)

    def write_symbols(self, records: Sequence[Record]) -> Path:
        if not records:
            raise ValueError("证券数据为空")
        cleaned = drop_duplicates(records, subset=["symbol"])
        cleaned = drop_na(cleaned, subset=["symbol", "name"])
        path = self.manager.path_for(DatasetKind.SYMBOLS)
        self._write_table(path, cleaned)
        _LOGGER.info("已写入证券主表", extra={"rows": len(cleaned), "path": str(path)})
        return path

    def write_trading_calendar(self, records: Sequence[Record]) -> Path:
        if not records:
            raise ValueError("交易日历数据为空")
        cleaned = drop_duplicates(records, subset=["date", "market"])
        path = self.manager.path_for(DatasetKind.TRADING_CALENDAR)
        self._write_table(path, cleaned)
        _LOGGER.info("已写入交易日历", extra={"rows": len(cleaned), "path": str(path)})
        return path

    def write_fundamentals(self, records: Sequence[Record]) -> None:
        if not records:
            return
        cleaned = drop_na(records, subset=["symbol", "date"])
        cleaned = drop_duplicates(cleaned, subset=["symbol", "date"])
        grouped: Dict[Tuple[str, int], List[Record]] = defaultdict(list)
        for record in cleaned:
            dt_value = record["date"]
            if isinstance(dt_value, datetime):
                target_date = dt_value.date()
            elif isinstance(dt_value, date):
                target_date = dt_value
            else:
                raise ValueError("字段 date 必须为 date/datetime 类型")
            dt_datetime = datetime.combine(target_date, datetime.min.time())
            record = {**record, "date": target_date, "_timestamp": dt_datetime}
            grouped[(str(record["symbol"]), target_date.year)].append(record)

        for (symbol, year), year_records in grouped.items():
            timestamp = datetime(year, 1, 1)
            path = self.manager.path_for(
                DatasetKind.FUNDAMENTALS,
                symbol=symbol,
                timestamp=timestamp,
            )
            normalised = [{k: v for k, v in r.items() if k != "_timestamp"} for r in year_records]
            combined = self._merge_existing(
                path,
                normalised,
                subset=("symbol", "date"),
                sort_key="date",
            )
            self._write_table(path, combined)
            _LOGGER.info(
                "已写入基础指标",
                extra={"symbol": symbol, "year": year, "rows": len(normalised), "path": str(path)},
            )

    def write_ohlcv(self, records: Sequence[Record], freq: str) -> None:
        if not records:
            return
        cleaned = drop_na(records, subset=["symbol", "dt"])
        cleaned = drop_duplicates(cleaned, subset=["symbol", "dt", "freq"])
        grouped = self._group_by_symbol(cleaned)
        for symbol, symbol_records in grouped.items():
            by_date = self._group_by_date(symbol_records)
            for day, day_records in by_date.items():
                timestamp = datetime.combine(day, datetime.min.time())
                kind = DatasetKind.OHLCV_DAILY if freq.upper() == "D" else DatasetKind.OHLCV_INTRADAY
                path = self.manager.path_for(
                    kind,
                    symbol=symbol,
                    freq=freq,
                    timestamp=timestamp,
                )
                combined = self._merge_existing(
                    path,
                    day_records,
                    subset=("symbol", "dt", "freq"),
                    sort_key="dt",
                )
                self._write_table(path, combined)
                _LOGGER.info(
                    "已写入行情数据",
                    extra={"symbol": symbol, "freq": freq, "rows": len(day_records), "path": str(path)},
                )

    def write_backtest_result(
        self,
        strategy_id: str,
        run_id: str,
        run_date: datetime,
        equity_curve: Sequence[Record],
        trades: Sequence[Record],
    ) -> Dict[str, Path]:
        path = self.manager.path_for(
            DatasetKind.BACKTEST_RESULTS,
            symbol=strategy_id,
            timestamp=run_date,
        )
        base_dir = path.parent
        base_dir.mkdir(parents=True, exist_ok=True)

        equity_path = base_dir / "equity.parquet"
        trade_path = base_dir / "trades.parquet"

        self._write_table(equity_path, equity_curve)
        self._write_table(trade_path, trades)

        _LOGGER.info(
            "已写入回测结果",
            extra={
                "strategy_id": strategy_id,
                "run_id": run_id,
                "equity_rows": len(equity_curve),
                "trade_rows": len(trades),
                "path": str(base_dir),
            },
        )
        return {"equity": equity_path, "trades": trade_path}

    def write_realtime_quotes(self, records: Sequence[Record]) -> None:
        if not records:
            return
        cleaned = drop_na(records, subset=["symbol", "snapshot_time"])
        cleaned = drop_duplicates(cleaned, subset=["symbol", "snapshot_time"])
        buckets: Dict[Path, List[Record]] = defaultdict(list)
        for record in cleaned:
            snapshot = record.get("snapshot_time")
            if isinstance(snapshot, datetime):
                snapshot_dt = snapshot
            else:
                snapshot_dt = datetime.fromisoformat(str(snapshot))
            normalised = {**record, "snapshot_time": snapshot_dt}
            path = self.manager.path_for(
                DatasetKind.REALTIME_QUOTES,
                symbol=str(record["symbol"]),
                timestamp=snapshot_dt,
            )
            buckets[path].append(normalised)

        for path, records_per_file in buckets.items():
            combined = self._merge_existing(
                path,
                records_per_file,
                subset=("symbol", "snapshot_time"),
                sort_key="snapshot_time",
            )
            self._write_table(path, combined)
            _LOGGER.info(
                "已写入实时行情",
                extra={"path": str(path), "rows": len(records_per_file)},
            )

    def write_trading_orders(
        self,
        session_id: str,
        strategy_id: str,
        timestamp: datetime,
        orders: Sequence[Record],
    ) -> None:
        if not orders:
            return
        normalized = self._ensure_datetime_field(orders, "created_at")
        path = self.manager.path_for(
            DatasetKind.TRADING_ORDERS,
            symbol=session_id,
            freq=strategy_id,
            timestamp=timestamp,
        )
        combined = self._merge_existing(
            path,
            normalized,
            subset=("order_id",),
            sort_key="created_at",
        )
        self._write_table(path, combined)
        _LOGGER.info(
            "已写入交易订单",
            extra={
                "session_id": session_id,
                "strategy_id": strategy_id,
                "rows": len(orders),
                "path": str(path),
            },
        )

    def write_trading_trades(
        self,
        session_id: str,
        strategy_id: str,
        timestamp: datetime,
        trades: Sequence[Record],
    ) -> None:
        if not trades:
            return
        normalized = self._ensure_datetime_field(trades, "timestamp")
        path = self.manager.path_for(
            DatasetKind.TRADING_TRADES,
            symbol=session_id,
            freq=strategy_id,
            timestamp=timestamp,
        )
        combined = self._merge_existing(
            path,
            normalized,
            subset=("trade_id",),
            sort_key="timestamp",
        )
        self._write_table(path, combined)
        _LOGGER.info(
            "已写入交易成交",
            extra={
                "session_id": session_id,
                "strategy_id": strategy_id,
                "rows": len(trades),
                "path": str(path),
            },
        )

    def write_trading_equity(
        self,
        session_id: str,
        strategy_id: str,
        snapshot: Record,
    ) -> None:
        normalized = self._ensure_datetime_field([snapshot], "timestamp")
        timestamp = normalized[0]["timestamp"]
        path = self.manager.path_for(
            DatasetKind.TRADING_EQUITY,
            symbol=session_id,
            freq=strategy_id,
            timestamp=timestamp,
        )
        combined = self._merge_existing(
            path,
            normalized,
            subset=("timestamp",),
            sort_key="timestamp",
        )
        self._write_table(path, combined)
        _LOGGER.info(
            "已写入交易权益",
            extra={
                "session_id": session_id,
                "strategy_id": strategy_id,
                "path": str(path),
            },
        )

    def latest_timestamp(self, symbol: str, freq: str) -> Optional[datetime]:
        kind = DatasetKind.OHLCV_DAILY if freq.upper() == "D" else DatasetKind.OHLCV_INTRADAY
        config: DatasetConfig = self.manager.get(kind)
        base = self.manager.base_dir / config.relative_dir / f"freq={freq}" / f"symbol={symbol}"
        if not base.exists():
            return None
        timestamps: List[datetime] = []
        for file_path in base.rglob("*.parquet"):
            table = pq.read_table(file_path)
            if "dt" in table.column_names:
                values = table.column("dt").to_pylist()
                timestamps.extend([value for value in values if isinstance(value, datetime)])
        if not timestamps:
            return None
        return max(timestamps)

    def _merge_existing(
        self,
        path: Path,
        new_records: Sequence[Record],
        *,
        subset: Tuple[str, ...],
        sort_key: str = "dt",
    ) -> List[Record]:
        if path.exists():
            existing = pq.read_table(path).to_pylist()
            combined = existing + list(new_records)
        else:
            combined = list(new_records)
        combined = drop_duplicates(combined, subset=subset)
        combined = sorted(combined, key=lambda record: record.get(sort_key))
        return combined

    @staticmethod
    def _ensure_datetime_field(records: Sequence[Record], field: str) -> List[Record]:
        normalized: List[Record] = []
        for record in records:
            value = record.get(field)
            if isinstance(value, datetime):
                dt_value = value
            elif isinstance(value, date):
                dt_value = datetime.combine(value, datetime.min.time())
            elif value is None:
                dt_value = datetime.utcnow()
            else:
                dt_value = datetime.fromisoformat(str(value))
            normalized.append({**record, field: dt_value})
        return normalized

    @staticmethod
    def _write_table(path: Path, records: Sequence[Record]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(list(records))
        pq.write_table(table, path)

    @staticmethod
    def _group_by_symbol(records: Sequence[Record]) -> Dict[str, List[Record]]:
        grouped: Dict[str, List[Record]] = defaultdict(list)
        for record in records:
            grouped[str(record["symbol"])].append(record)
        return grouped

    @staticmethod
    def _group_by_date(records: Sequence[Record]) -> Dict[date, List[Record]]:
        grouped: Dict[date, List[Record]] = defaultdict(list)
        for record in records:
            dt_value: datetime = record["dt"]
            grouped[dt_value.date()].append(record)
        return grouped


__all__ = ["ParquetRepository"]
