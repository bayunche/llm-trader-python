"""API 辅助函数。"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from llm_trader.data import DatasetKind, default_manager


def load_symbols() -> pd.DataFrame:
    manager = default_manager()
    path = manager.path_for(DatasetKind.SYMBOLS)
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "name", "board", "status", "listed_date", "delisted_date"])
    return pd.read_parquet(path)


def resolve_ohlcv_files(symbol: str, freq: str) -> List[Path]:
    manager = default_manager()
    kind = DatasetKind.OHLCV_DAILY if freq.upper() == "D" else DatasetKind.OHLCV_INTRADAY
    config = manager.get(kind)
    base = manager.base_dir / config.relative_dir / f"freq={freq}" / f"symbol={symbol}"
    if not base.exists():
        return []
    return sorted(base.rglob("*.parquet"))


def load_ohlcv(symbols: Iterable[str], freq: str, start: Optional[datetime], end: Optional[datetime]) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for symbol in symbols:
        files = resolve_ohlcv_files(symbol, freq)
        if not files:
            continue
        frames = [pd.read_parquet(file) for file in files]
        df = pd.concat(frames, ignore_index=True)
        df["dt"] = pd.to_datetime(df["dt"])
        if start:
            df = df[df["dt"] >= start]
        if end:
            df = df[df["dt"] <= end]
        df = df.sort_values("dt")
        for _, row in df.iterrows():
            records.append(row.to_dict())
    return records


def _load_parquet_records(path: Path, sort_key: str, limit: Optional[int] = None) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    df = pd.read_parquet(path)
    if df.empty:
        return []
    df = df.sort_values(sort_key)
    if limit:
        df = df.tail(limit)
    return [
        {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def load_trading_orders(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[Dict[str, object]]:
    manager = default_manager()
    config = manager.get(DatasetKind.TRADING_ORDERS)
    base = manager.base_dir / config.relative_dir / f"session={session_id}" / f"strategy={strategy_id}"
    if not base.exists():
        return []
    records: List[Dict[str, object]] = []
    for file_path in sorted(base.rglob("*.parquet")):
        records.extend(_load_parquet_records(file_path, "created_at"))
    if not records:
        return []
    records.sort(key=lambda item: item.get("created_at", ""))
    if limit:
        records = records[-limit:]
    return records


def load_trading_trades(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[Dict[str, object]]:
    manager = default_manager()
    config = manager.get(DatasetKind.TRADING_TRADES)
    base = manager.base_dir / config.relative_dir / f"session={session_id}" / f"strategy={strategy_id}"
    if not base.exists():
        return []
    records: List[Dict[str, object]] = []
    for file_path in sorted(base.rglob("*.parquet")):
        records.extend(_load_parquet_records(file_path, "timestamp"))
    if not records:
        return []
    records.sort(key=lambda item: item.get("timestamp", ""))
    if limit:
        records = records[-limit:]
    return records


def load_trading_equity(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[Dict[str, object]]:
    manager = default_manager()
    config = manager.get(DatasetKind.TRADING_EQUITY)
    path = manager.base_dir / config.relative_dir / f"session={session_id}" / f"strategy={strategy_id}" / config.filename_template
    # filename_template = equity.parquet
    if not path.exists():
        return []
    records = _load_parquet_records(path, "timestamp", limit)
    for item in records:
        positions = item.get("positions")
        if isinstance(positions, str):
            try:
                item["positions"] = json.loads(positions)
            except json.JSONDecodeError:
                pass
    return records


def load_llm_logs(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[Dict[str, object]]:
    manager = default_manager()
    config = manager.get(DatasetKind.STRATEGY_LLM_LOGS)
    base = manager.base_dir / config.relative_dir / f"strategy={strategy_id}" / f"session={session_id}"
    if not base.exists():
        return []
    entries: List[Dict[str, object]] = []
    for file_path in sorted(base.rglob("logs.jsonl")):
        with file_path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(record)
    entries.sort(key=lambda item: item.get("timestamp", ""))
    if limit:
        entries = entries[-limit:]
    return entries


def load_trading_runs(
    strategy_id: str,
    session_id: str,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, object]]:
    manager = default_manager()
    path = manager.path_for(
        DatasetKind.TRADING_RUNS,
        symbol=strategy_id,
        freq=session_id,
        ensure_dir=False,
    )
    if not path.exists():
        return []
    df = pd.read_parquet(path)
    if df.empty:
        return []
    df = df.sort_values("timestamp")
    if offset > 0:
        df = df.iloc[offset:]
    if limit is not None:
        df = df.tail(limit)
    records = df.to_dict("records")
    for item in records:
        ts = item.get("timestamp")
        if isinstance(ts, datetime):
            item["timestamp"] = ts.isoformat()
        for field in ("selected_symbols", "rules", "alerts", "indicators"):
            value = item.get(field)
            if isinstance(value, str):
                try:
                    item[field] = json.loads(value)
                except json.JSONDecodeError:
                    continue
        # 兼容历史记录缺失字段
        item.setdefault("selected_symbols", [])
        item.setdefault("rules", [])
        item.setdefault("alerts", [])
        item.setdefault("indicators", [])
    return records
