"""策略引擎测试。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from llm_trader.strategy.engine import RuleConfig, StrategyEngine
from llm_trader.strategy.signals import generate_orders_from_signals


def test_strategy_engine_generates_signals() -> None:
    data = pd.DataFrame(
        {
            "open": [10, 10.5, 11, 10.8, 10.6, 10.9],
            "close": [10.1, 10.6, 11.1, 10.7, 10.5, 11.0],
        },
        index=pd.date_range("2024-07-01", periods=6, freq="D"),
    )
    rules = [
        RuleConfig(indicator="sma", column="close", params={"window": 3}, operator=">", threshold=10.6)
    ]
    engine = StrategyEngine(rules)
    result = engine.evaluate(data)
    assert "signal" in result.columns
    assert result["signal"].iloc[-1] in {0, 1, -1}


def test_generate_orders_from_signals() -> None:
    index = pd.date_range("2024-07-01", periods=3, freq="D")
    df = pd.DataFrame({"signal": [0, 1, -1], "open": [10, 10.5, 10.8]}, index=index)
    orders = generate_orders_from_signals(df, symbol="600000.SH", volume_per_trade=100)
    assert len(orders) == 2
    assert orders[0].side.value == "buy"
    assert orders[1].side.value == "sell"
