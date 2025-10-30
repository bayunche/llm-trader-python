"""回测绩效指标计算。"""

from __future__ import annotations

from math import sqrt
from typing import Dict, Sequence


def compute_metrics(equity_curve: Sequence[Dict[str, float]]) -> Dict[str, float]:
    if not equity_curve:
        return {}
    equity_values = [item["equity"] for item in equity_curve]
    start = equity_values[0]
    end = equity_values[-1]
    total_return = (end - start) / start if start else 0.0
    periods = len(equity_values)
    annual_return = (1 + total_return) ** (252 / max(periods, 1)) - 1 if periods > 1 else total_return

    peak = equity_values[0]
    max_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        drawdown = (value - peak) / peak if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)

    returns = []
    for i in range(1, len(equity_values)):
        prev = equity_values[i - 1]
        curr = equity_values[i]
        if prev:
            returns.append((curr - prev) / prev)
    if returns:
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std = sqrt(variance)
        sharpe_ratio = (avg_return / std) * sqrt(252) if std else 0.0
    else:
        sharpe_ratio = 0.0

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
    }
