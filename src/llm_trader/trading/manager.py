"""受控交易执行管理器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from llm_trader.config import get_settings

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
        policy = RiskPolicy(
            RiskThresholds(
                max_equity_drawdown=settings.max_equity_drawdown,
                max_position_ratio=settings.max_position_ratio,
            )
        )

    result = run_ai_trading_cycle(config, trading_session=trading_session, **kwargs)
    session: TradingSession = result["session"]
    equity_curve = session.account.equity_curve
    positions = session.snapshot_positions()
    decision = policy.evaluate(equity_curve, positions)
    return ManagedTradingResult(decision=decision, raw_result=result)


__all__ = ["ManagedTradingResult", "run_managed_trading_cycle"]
