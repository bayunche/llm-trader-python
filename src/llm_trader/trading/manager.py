"""受控交易执行管理器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from llm_trader.config import get_settings
from llm_trader.data import DatasetKind, default_manager
from llm_trader.monitoring import AlertEmitter
from .alerts import TradingAlertService

from .orchestrator import TradingCycleConfig, run_ai_trading_cycle
from .policy import RiskDecision, RiskPolicy, RiskThresholds
from .session import TradingSession
from llm_trader.db.models.enums import DecisionStatus


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
    quotes: Optional[List[Dict[str, object]]] = None,
    observation_id: Optional[str] = None,
    observation: Optional[object] = None,
    actor_service=None,
    checker_service=None,
    decision_service=None,
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

    result = run_ai_trading_cycle(
        config,
        trading_session=trading_session,
        quotes=quotes,
        observation_id=observation_id,
        observation=observation,
        actor_service=actor_service,
        checker_service=checker_service,
        decision_service=decision_service,
        **kwargs,
    )
    session: TradingSession = result["session"]
    equity_curve = session.account.equity_curve
    positions = session.snapshot_positions()
    decision = policy.evaluate(equity_curve, positions)
    if decision_service and result.get("decision"):
        actor_decision = result["decision"]
        decision_id = actor_decision.decision_id
        evaluated_at = datetime.now(tz=timezone.utc)
        risk_record = decision_service.record_risk_result(
            decision_id=decision_id,
            passed=decision.proceed,
            reasons=list(decision.alerts),
            corrections=[],
            evaluated_at=evaluated_at,
        )
        result["risk_record"] = risk_record
        observation_ref = (
            actor_decision.observations_ref
            or observation_id
            or result.get("observation_id")
            or ""
        )
        if observation_ref:
            status = DecisionStatus.EXECUTED if decision.proceed else DecisionStatus.REJECTED_RISK
            ledger_record = decision_service.record_ledger(
                decision_id=decision_id,
                observation_id=observation_ref,
                actor_model=config.llm_model,
                checker_model=config.llm_model,
                status=status,
                risk_summary={"alerts": decision.alerts, "proceed": decision.proceed},
                executed_at=evaluated_at if decision.proceed else None,
            )
            result["decision_ledger"] = ledger_record
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
