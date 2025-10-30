"""仪表盘数据访问封装。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from llm_trader.api.utils import (
    load_llm_logs,
    load_trading_equity,
    load_trading_orders,
    load_trading_trades,
)
from llm_trader.data import DatasetKind, default_manager
from llm_trader.strategy import StrategyRepository, StrategyVersion


def _repository(base_dir: Optional[Path] = None) -> StrategyRepository:
    return StrategyRepository(base_dir=base_dir)


def get_orders(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[dict]:
    """获取订单流水。"""

    return load_trading_orders(strategy_id=strategy_id, session_id=session_id, limit=limit)


def get_trades(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[dict]:
    """获取成交记录。"""

    return load_trading_trades(strategy_id=strategy_id, session_id=session_id, limit=limit)


def get_equity_curve(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[dict]:
    """获取资金曲线与仓位快照。"""

    return load_trading_equity(strategy_id=strategy_id, session_id=session_id, limit=limit)


def get_llm_logs(strategy_id: str, session_id: str, limit: Optional[int] = None) -> List[dict]:
    """获取大模型策略日志。"""

    return load_llm_logs(strategy_id=strategy_id, session_id=session_id, limit=limit)


def list_strategy_versions(strategy_id: str) -> List[StrategyVersion]:
    """列出策略版本信息。"""

    repo = _repository()
    return repo.list_versions(strategy_id)


def list_strategy_ids() -> List[str]:
    """获取所有存在版本或交易数据的策略 ID。"""

    repo = _repository()
    versions = repo.list_versions()
    strategy_ids = {version.strategy_id for version in versions}
    # 补充仅存在交易数据的策略
    manager = default_manager()
    orders_config = manager.get(DatasetKind.TRADING_ORDERS)
    base = manager.base_dir / orders_config.relative_dir
    if base.exists():
        for session_dir in base.glob("session=*"):
            for strategy_dir in session_dir.glob("strategy=*"):
                strategy_ids.add(strategy_dir.name.split("=", 1)[1])
    return sorted(strategy_ids)


def list_strategy_sessions() -> List[Dict[str, str]]:
    """获取策略与会话映射列表。"""

    manager = default_manager()
    orders_config = manager.get(DatasetKind.TRADING_ORDERS)
    base = manager.base_dir / orders_config.relative_dir
    results: List[Dict[str, str]] = []
    if not base.exists():
        return results
    for session_dir in sorted(base.glob("session=*")):
        session_id = session_dir.name.split("=", 1)[1]
        for strategy_dir in sorted(session_dir.glob("strategy=*")):
            strategy_id = strategy_dir.name.split("=", 1)[1]
            results.append({"strategy_id": strategy_id, "session_id": session_id})
    return results


__all__ = [
    "get_orders",
    "get_trades",
    "get_equity_curve",
    "get_llm_logs",
    "list_strategy_versions",
    "list_strategy_ids",
    "list_strategy_sessions",
]
