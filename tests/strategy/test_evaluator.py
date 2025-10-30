"""策略评估测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.strategy.evaluator import select_and_register_best
from llm_trader.strategy.generator import StrategyCandidate
from llm_trader.strategy.repository import StrategyRepository
from llm_trader.strategy.engine import RuleConfig


def test_select_and_register_best(tmp_path) -> None:
    repo = StrategyRepository(base_dir=tmp_path)
    candidates = [
        StrategyCandidate(
            rules=[RuleConfig(indicator="sma", column="close", params={"window": 3}, operator=">", threshold=10.5)],
            metrics={"annual_return": 0.15},
            equity_curve=[{"date": datetime(2024, 7, 1), "equity": 100000.0}],
        ),
        StrategyCandidate(
            rules=[RuleConfig(indicator="ema", column="close", params={"span": 5}, operator=">", threshold=10.4)],
            metrics={"annual_return": 0.10},
            equity_curve=[{"date": datetime(2024, 7, 1), "equity": 100000.0}],
        ),
    ]
    result = select_and_register_best("demo", candidates, repo)
    assert result.strategy_id == "demo"
    versions = repo.list_versions("demo")
    assert len(versions) == 1
    assert versions[0].metrics["annual_return"] == 0.15
