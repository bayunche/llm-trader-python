#!/usr/bin/env python3
"""执行带风控策略的 AI 交易循环。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta

from llm_trader.trading import TradingCycleConfig, RiskPolicy, RiskThresholds
from llm_trader.trading.manager import run_managed_trading_cycle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run managed AI trading cycle")
    parser.add_argument("--session", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--indicators", nargs="+", default=["sma", "ema"])
    parser.add_argument("--freq", default="D")
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-drawdown", type=float, default=None, help="最大回撤阈值，例如 0.1")
    parser.add_argument("--max-position-ratio", type=float, default=None, help="单标的最大仓位占比，例如 0.3")
    parser.add_argument("--no-only-latest", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    history_end = datetime.utcnow()
    history_start = history_end - timedelta(days=args.lookback_days)

    config = TradingCycleConfig(
        session_id=args.session,
        strategy_id=args.strategy,
        symbols=args.symbols,
        objective=args.objective,
        indicators=args.indicators,
        freq=args.freq,
        history_start=history_start,
        history_end=history_end,
        initial_cash=args.initial_cash,
        llm_model=args.model,
        only_latest_bar=not args.no_only_latest,
    )

    thresholds = RiskThresholds()
    if args.max_drawdown is not None:
        thresholds.max_equity_drawdown = args.max_drawdown
    if args.max_position_ratio is not None:
        thresholds.max_position_ratio = args.max_position_ratio

    policy = RiskPolicy(thresholds)
    outcome = run_managed_trading_cycle(config, policy=policy)

    payload = {
        "decision": outcome.decision.proceed,
        "alerts": outcome.decision.alerts,
        "orders_executed": outcome.raw_result["orders_executed"],
        "trades_filled": outcome.raw_result["trades_filled"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    if not outcome.decision.proceed:
        exit(1)


if __name__ == "__main__":
    main()
