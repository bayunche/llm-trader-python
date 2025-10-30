"""策略搜索与优化模块。"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Dict, Iterable, List, Sequence

import pandas as pd

from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Sequence

import pandas as pd

from llm_trader.backtest import BacktestRunner, Order
from llm_trader.strategy.engine import RuleConfig, StrategyEngine
from llm_trader.strategy.signals import generate_orders_from_signals


@dataclass
class RuleSpace:
    """单条规则的搜索空间定义。"""

    indicator: str
    column: str
    params_grid: Dict[str, Iterable[int | float]]
    operators: Sequence[str]
    thresholds: Sequence[float]


@dataclass
class StrategyCandidate:
    rules: List[RuleConfig]
    metrics: Dict[str, float]
    equity_curve: List[Dict[str, float]]


@dataclass
class StrategyGenerator:
    runner: BacktestRunner
    long_only: bool = True
    top_n: int = 5
    min_trades: int = 1
    results: List[StrategyCandidate] = field(default_factory=list)

    def search(
        self,
        bars: Iterable[Dict],
        rule_spaces: Sequence[RuleSpace],
        *,
        strategy_id: str = "auto",
    ) -> List[StrategyCandidate]:
        candidates: List[StrategyCandidate] = []
        df = pd.DataFrame(bars)
        df["dt"] = pd.to_datetime(df["dt"])
        symbols = df["symbol"].unique().tolist() if "symbol" in df.columns else ["AUTO"]

        for combo in self._iter_rule_combinations(rule_spaces):
            orders_by_date: Dict[datetime, List[Order]] = defaultdict(list)
            for symbol in symbols:
                symbol_df = df[df["symbol"] == symbol].copy() if "symbol" in df.columns else df.copy()
                symbol_df.set_index("dt", inplace=True)
                engine = StrategyEngine(combo, long_only=self.long_only)
                evaluated = engine.evaluate(symbol_df)
                evaluated["symbol"] = symbol
                orders = generate_orders_from_signals(evaluated, symbol=symbol)
                for order in orders:
                    orders_by_date[order.created_at].append(order)

            result = self.runner.run(
                bars,
                lambda dt, *_: orders_by_date.get(dt, []),
                strategy_id=strategy_id,
                persist=False,
            )
            if len(result.trades) < self.min_trades:
                continue

            candidates.append(
                StrategyCandidate(
                    rules=combo,
                    metrics=result.metrics,
                    equity_curve=result.equity_curve,
                )
            )

        candidates.sort(key=lambda c: c.metrics.get("annual_return", 0.0), reverse=True)
        self.results = candidates[: self.top_n]
        return self.results

    def _iter_rule_combinations(self, rule_spaces: Sequence[RuleSpace]) -> Iterable[List[RuleConfig]]:
        for space in rule_spaces:
            param_keys = list(space.params_grid.keys())
            param_values = [space.params_grid[key] for key in param_keys]
            for operator in space.operators:
                for threshold in space.thresholds:
                    for param_combo in product(*param_values):
                        params = dict(zip(param_keys, param_combo))
                        yield [
                            RuleConfig(
                                indicator=space.indicator,
                                column=space.column,
                                params=params,
                                operator=operator,
                                threshold=threshold,
                            )
                        ]
