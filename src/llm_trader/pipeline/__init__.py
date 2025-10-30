"""自动化交易管道导出。"""

from .auto import (
    BacktestCriteria,
    AutoTradingConfig,
    AutoTradingResult,
    run_full_automation,
)

__all__ = [
    "BacktestCriteria",
    "AutoTradingConfig",
    "AutoTradingResult",
    "run_full_automation",
]
