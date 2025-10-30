#!/usr/bin/env python3
"""启动受控交易调度器。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from llm_trader.trading import RiskPolicy, RiskThresholds
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.tasks.managed_cycle import start_managed_scheduler


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start managed trading scheduler")
    parser.add_argument("--session", nargs="+", required=True, help="会话 ID 列表")
    parser.add_argument("--strategy", nargs="+", required=True, help="策略 ID 列表，与会话按索引对应")
    parser.add_argument("--symbols", nargs="+", required=True, help="符号列表，使用逗号分隔")
    parser.add_argument("--objective", required=True, help="策略目标描述")
    parser.add_argument("--interval", type=int, default=60, help="调度间隔（分钟）")
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-drawdown", type=float, default=None)
    parser.add_argument("--max-position-ratio", type=float, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if len(args.session) != len(args.strategy):
        raise ValueError("会话与策略数量必须一致")

    now = datetime.utcnow()
    configs = []
    symbols = args.symbols
    if len(args.symbols) == 1 and "," in args.symbols[0]:
        symbols = [symbol.strip() for symbol in args.symbols[0].split(",") if symbol.strip()]

    for session_id, strategy_id in zip(args.session, args.strategy):
        configs.append(
            TradingCycleConfig(
                session_id=session_id,
                strategy_id=strategy_id,
                symbols=symbols,
                objective=args.objective,
                history_start=now - timedelta(days=args.lookback_days),
                history_end=now,
                llm_model=args.model,
            )
        )

    thresholds = RiskThresholds()
    if args.max_drawdown is not None:
        thresholds.max_equity_drawdown = args.max_drawdown
    if args.max_position_ratio is not None:
        thresholds.max_position_ratio = args.max_position_ratio

    policy = RiskPolicy(thresholds)
    scheduler = start_managed_scheduler(configs, interval_minutes=args.interval, policy=policy)

    try:
        scheduler.print_jobs()
        while True:
            scheduler._event.wait(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
