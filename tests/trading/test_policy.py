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


def test_risk_policy_detects_volatility() -> None:
    thresholds = RiskThresholds(
        max_equity_drawdown=1.0,
        max_position_ratio=1.0,
        max_equity_volatility=0.01,
    )
    policy = RiskPolicy(thresholds)
    equity_curve = [
        {"timestamp": datetime(2024, 1, 1), "equity": 100000.0},
        {"timestamp": datetime(2024, 1, 2), "equity": 120000.0},
        {"timestamp": datetime(2024, 1, 3), "equity": 90000.0},
    ]
    decision = policy.evaluate(equity_curve, [])
    assert not decision.proceed
    assert any("波动率" in alert for alert in decision.alerts)


def test_risk_policy_detects_sector_exposure() -> None:
    thresholds = RiskThresholds(
        max_equity_drawdown=1.0,
        max_position_ratio=1.0,
        max_sector_exposure=0.4,
    )
    policy = RiskPolicy(thresholds, sector_lookup=lambda symbol: "银行" if symbol == "600000.SH" else "UNKNOWN")
    equity_curve = [
        {"timestamp": datetime(2024, 1, 2), "equity": 100000.0},
    ]
    positions = [
        {"symbol": "600000.SH", "volume": 1000, "cost_price": 50.0},
        {"symbol": "000001.SZ", "volume": 100, "cost_price": 5.0},
    ]
    decision = policy.evaluate(equity_curve, positions)
    assert not decision.proceed
    assert any("行业" in alert for alert in decision.alerts)


def test_risk_policy_detects_holding_period() -> None:
    thresholds = RiskThresholds(
        max_equity_drawdown=1.0,
        max_position_ratio=1.0,
        max_holding_days=10,
    )
    policy = RiskPolicy(thresholds)
    reference = datetime(2024, 1, 20)
    equity_curve = [
        {"timestamp": reference, "equity": 100000.0},
    ]
    positions = [
        {
            "symbol": "600000.SH",
            "volume": 1000,
            "cost_price": 10.0,
            "lots": [
                {"volume": 1000, "cost_price": 10.0, "acquired_at": "2023-12-20T09:30:00"},
            ],
        }
    ]
    decision = policy.evaluate(equity_curve, positions)
    assert not decision.proceed
    assert any("持仓" in alert for alert in decision.alerts)
