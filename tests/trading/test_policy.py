"""风险控制策略测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.trading.policy import RiskDecision, RiskPolicy, RiskThresholds


def test_risk_policy_detects_drawdown_and_exposure() -> None:
    policy = RiskPolicy(RiskThresholds(max_equity_drawdown=0.05, max_position_ratio=0.4))
    equity_curve = [
        {"timestamp": datetime(2024, 1, 1), "equity": 100000.0},
        {"timestamp": datetime(2024, 1, 2), "equity": 94000.0},
    ]
    positions = [
        {"symbol": "600000.SH", "volume": 1000, "cost_price": 90.0},
    ]
    decision = policy.evaluate(equity_curve, positions)
    assert isinstance(decision, RiskDecision)
    assert not decision.proceed
    assert len(decision.alerts) >= 2
