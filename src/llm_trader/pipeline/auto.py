"""全链路自动交易管道。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from llm_trader.api.utils import load_ohlcv
from llm_trader.backtest import BacktestRunner, Order
from llm_trader.backtest.models import OrderSide
from llm_trader.trading import TradingCycleConfig, run_managed_trading_cycle
from llm_trader.trading.manager import ManagedTradingResult
from llm_trader.strategy import generate_orders_from_signals
from llm_trader.strategy.engine import RuleConfig, StrategyEngine
from llm_trader.trading.orchestrator import run_ai_trading_cycle


@dataclass
class BacktestCriteria:
    """回测验收标准。"""

    min_total_return: float = 0.0
    max_drawdown: float = 0.2


@dataclass
class AutoTradingConfig:
    """全链路自动交易配置。"""

    trading: TradingCycleConfig
    backtest_start: datetime
    backtest_end: datetime
    criteria: BacktestCriteria = BacktestCriteria()
    run_backtest: bool = True


@dataclass
class AutoTradingResult:
    status: str
    backtest_metrics: Optional[Dict[str, float]]
    managed_result: Optional[ManagedTradingResult]


def run_full_automation(
    config: AutoTradingConfig,
    *,
    trading_session=None,
    load_ohlcv_fn=load_ohlcv,
) -> AutoTradingResult:
    """执行从策略生成到风险控制的全链路流程。"""

    trading_result = run_ai_trading_cycle(config.trading, trading_session=trading_session)
    suggestion = trading_result["suggestion"]

    backtest_metrics: Optional[Dict[str, float]] = None

    if config.run_backtest:
        bars = load_ohlcv_fn(
            config.trading.symbols,
            config.trading.freq,
            config.backtest_start,
            config.backtest_end,
        )
        if not bars:
            return AutoTradingResult("backtest_missing_data", None, None)

        runner = BacktestRunner()
        orders_by_date = _prepare_orders_for_backtest(bars, suggestion.rules)

        def provider(dt: datetime, *_args) -> List[Order]:
            return orders_by_date.get(dt, [])

        result = runner.run(
            bars,
            provider,
            strategy_id=config.trading.strategy_id,
            run_id="auto",
            persist=False,
        )
        backtest_metrics = result.metrics
        if not _pass_criteria(backtest_metrics, config.criteria):
            return AutoTradingResult("backtest_rejected", backtest_metrics, None)

    managed = run_managed_trading_cycle(
        config.trading,
        trading_session=trading_result["session"],
    )
    status = "executed" if managed.decision.proceed else "risk_blocked"
    return AutoTradingResult(status, backtest_metrics, managed)


def _prepare_orders_for_backtest(
    bars: List[Dict[str, object]],
    rules: List[RuleConfig],
) -> Dict[datetime, List[Order]]:
    df = pd.DataFrame(bars)
    df["dt"] = pd.to_datetime(df["dt"])
    orders_by_date: Dict[datetime, List[Order]] = {}
    engine = StrategyEngine(rules)

    for symbol, group in df.groupby("symbol"):
        group = group.set_index("dt").sort_index()
        evaluated = engine.evaluate(group)
        evaluated["symbol"] = symbol
        orders = generate_orders_from_signals(evaluated, symbol=symbol)
        for order in orders:
            orders_by_date.setdefault(order.created_at, []).append(order)
    return orders_by_date


def _pass_criteria(metrics: Dict[str, float], criteria: BacktestCriteria) -> bool:
    total_return = metrics.get("total_return", 0.0)
    max_drawdown = abs(metrics.get("max_drawdown", 0.0))
    if total_return < criteria.min_total_return:
        return False
    if max_drawdown > criteria.max_drawdown:
        return False
    return True


__all__ = [
    "BacktestCriteria",
    "AutoTradingConfig",
    "AutoTradingResult",
    "run_full_automation",
]


def _main() -> None:  # pragma: no cover - 简易 CLI
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run full auto trading pipeline")
    parser.add_argument("--session", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--backtest-start", required=True)
    parser.add_argument("--backtest-end", required=True)
    parser.add_argument("--min-return", type=float, default=0.0)
    parser.add_argument("--max-drawdown", type=float, default=0.2)
    args = parser.parse_args()

    trading_cfg = TradingCycleConfig(
        session_id=args.session,
        strategy_id=args.strategy,
        symbols=args.symbols,
        objective=args.objective,
        history_start=datetime.fromisoformat(args.backtest_start),
    )
    auto_cfg = AutoTradingConfig(
        trading=trading_cfg,
        backtest_start=datetime.fromisoformat(args.backtest_start),
        backtest_end=datetime.fromisoformat(args.backtest_end),
        criteria=BacktestCriteria(min_total_return=args.min_return, max_drawdown=args.max_drawdown),
    )
    result = run_full_automation(auto_cfg)
    payload = {
        "status": result.status,
        "backtest": result.backtest_metrics,
        "risk_alerts": [] if result.managed_result is None else result.managed_result.decision.alerts,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    _main()
