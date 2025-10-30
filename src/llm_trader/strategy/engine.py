"""策略引擎。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import pandas as pd

from llm_trader.strategy.library.indicators import get_indicator


@dataclass
class RuleConfig:
    indicator: str
    column: str
    params: Dict[str, int | float]
    operator: str
    threshold: float


class StrategyEngine:
    def __init__(self, rules: Sequence[RuleConfig], long_only: bool = True) -> None:
        self.rules = list(rules)
        self.long_only = long_only

    def evaluate(self, df: pd.DataFrame) -> pd.DataFrame:
        working = df.copy()
        signals = pd.Series(True, index=working.index)
        for idx, rule in enumerate(self.rules):
            indicator_fn = get_indicator(rule.indicator)
            series = indicator_fn(working[rule.column], **rule.params)
            op = rule.operator
            if op == ">":
                mask = series > rule.threshold
            elif op == ">=":
                mask = series >= rule.threshold
            elif op == "<":
                mask = series < rule.threshold
            elif op == "<=":
                mask = series <= rule.threshold
            elif op == "cross_up":
                mask = (series > rule.threshold) & (series.shift(1) <= rule.threshold)
            elif op == "cross_down":
                mask = (series < rule.threshold) & (series.shift(1) >= rule.threshold)
            else:
                raise ValueError(f"不支持的比较符：{op}")
            signals = signals & mask.fillna(False)
            working[f"rule_{idx}"] = mask
        working["entry"] = signals
        working["exit"] = signals.ne(signals.shift(1)).fillna(False) & (~signals)
        working["signal"] = 0
        working.loc[working["entry"], "signal"] = 1
        working.loc[working["exit"], "signal"] = -1 if not self.long_only else 0
        working["position"] = working["signal"].replace({0: None}).ffill().fillna(0)
        return working
