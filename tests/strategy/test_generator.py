"""策略生成器测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.backtest import BacktestRunner
from llm_trader.data import default_manager
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.strategy.generator import RuleSpace, StrategyGenerator


def test_strategy_generator_returns_candidates(tmp_path) -> None:
    bars = [
        {"dt": datetime(2024, 7, 1), "symbol": "600000.SH", "open": 10.0, "close": 10.1},
        {"dt": datetime(2024, 7, 2), "symbol": "600000.SH", "open": 10.2, "close": 10.4},
        {"dt": datetime(2024, 7, 3), "symbol": "600000.SH", "open": 10.5, "close": 10.7},
        {"dt": datetime(2024, 7, 4), "symbol": "600000.SH", "open": 10.8, "close": 10.6},
    ]
    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    runner = BacktestRunner(initial_cash=100000.0, repository=repository)

    space = RuleSpace(
        indicator="sma",
        column="close",
        params_grid={"window": [2, 3]},
        operators=[">"],
        thresholds=[10.3, 10.6],
    )
    generator = StrategyGenerator(runner=runner, top_n=2, min_trades=0)
    candidates = generator.search(bars, [space], strategy_id="test")
    assert len(candidates) <= 2
    assert candidates[0].metrics is not None
