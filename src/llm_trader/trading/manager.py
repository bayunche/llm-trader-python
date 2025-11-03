"""受控交易执行管理器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from llm_trader.config import get_settings
from llm_trader.data import DatasetKind, default_manager
from llm_trader.monitoring import AlertEmitter
from .alerts import TradingAlertService

from .orchestrator import TradingCycleConfig, run_ai_trading_cycle
from .policy import RiskDecision, RiskPolicy, RiskThresholds
from .session import TradingSession


@dataclass
class ManagedTradingResult:
    """受控交易执行结果。"""

    decision: RiskDecision
    raw_result: Dict[str, Any]


def run_managed_trading_cycle(
    config: TradingCycleConfig,
    *,
    policy: Optional[RiskPolicy] = None,
    trading_session: Optional[TradingSession] = None,
    **kwargs: Any,
) -> ManagedTradingResult:
    """运行带风险控制的交易循环。"""

    if policy is None:
        settings = get_settings().risk
        sector_lookup = _build_sector_lookup()
        policy = RiskPolicy(
            RiskThresholds(
                max_equity_drawdown=settings.max_equity_drawdown,
                max_position_ratio=settings.max_position_ratio,
                max_equity_volatility=settings.max_equity_volatility,
                max_sector_exposure=settings.max_sector_exposure,
                max_holding_days=settings.max_holding_days,
            ),
            sector_lookup=sector_lookup,
        )

    result = run_ai_trading_cycle(config, trading_session=trading_session, **kwargs)
    session: TradingSession = result["session"]
    equity_curve = session.account.equity_curve
    positions = session.snapshot_positions()
    decision = policy.evaluate(equity_curve, positions)
    if not decision.proceed:
        alert = TradingAlertService(AlertEmitter(channel=get_settings().monitoring.channel))
        reason = "; ".join(decision.alerts) if decision.alerts else "风控阈值触发"
        alert.risk_blocked(
            strategy_id=config.strategy_id,
            session_id=config.session_id,
            reason=reason,
        )
    return ManagedTradingResult(decision=decision, raw_result=result)


def _build_sector_lookup() -> Callable[[str], Optional[str]]:
    """构建行业映射查询函数，用于行业集中度校验。"""

    try:
        import pyarrow.parquet as pq
    except ImportError:  # pragma: no cover - 缺少依赖时跳过行业检查
        return lambda _symbol: None

    manager = default_manager()
    try:
        path = manager.path_for(DatasetKind.SYMBOLS, ensure_dir=False)
    except KeyError:
        return lambda _symbol: None
    if not path.exists():
        return lambda _symbol: None
    try:
        table = pq.read_table(path, columns=["symbol", "industry"])
    except Exception:  # pragma: no cover - parquet 读取失败时忽略
        return lambda _symbol: None
    records = table.to_pylist()
    mapping: Dict[str, str] = {}
    for record in records:
        symbol = record.get("symbol")
        if not symbol:
            continue
        industry = record.get("industry") or "未知"
        mapping[str(symbol)] = str(industry)

    def lookup(symbol: str) -> Optional[str]:
        return mapping.get(symbol)

    return lookup


__all__ = ["ManagedTradingResult", "run_managed_trading_cycle"]
