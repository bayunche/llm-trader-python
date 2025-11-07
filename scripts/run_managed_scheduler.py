#!/usr/bin/env python3
"""启动受控交易调度器。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from llm_trader.config import get_settings
from llm_trader.trading import RiskPolicy, RiskThresholds
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.tasks.managed_cycle import start_managed_scheduler
from llm_trader.scheduler import export_scheduler_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start managed trading scheduler")
    parser.add_argument("--session", nargs="+", help="会话 ID 列表，默认读取 TRADING_SESSION")
    parser.add_argument("--strategy", nargs="+", help="策略 ID 列表，与会话按索引对应，默认读取 TRADING_STRATEGY")
    parser.add_argument("--symbols", nargs="+", help="符号列表，使用逗号分隔，默认读取 TRADING_SYMBOLS")
    parser.add_argument("--objective", help="策略目标描述，默认读取 TRADING_OBJECTIVE")
    parser.add_argument("--interval", type=int, default=None, help="调度间隔（分钟），默认读取 TRADING_SCHEDULER_INTERVAL")
    parser.add_argument("--lookback-days", type=int, default=None, help="历史回看天数，默认读取 TRADING_LOOKBACK_DAYS")
    parser.add_argument("--model", default=None, help="大模型名称，默认读取 TRADING_LLM_MODEL")
    parser.add_argument("--llm-base-url", default=None, help="OpenAI 兼容接口 Base URL，默认读取 TRADING_LLM_BASE_URL")
    parser.add_argument("--max-drawdown", type=float, default=None)
    parser.add_argument("--max-position-ratio", type=float, default=None)
    parser.add_argument(
        "--execution-mode",
        choices=["sandbox", "live"],
        default=None,
        help="交易执行模式（默认读取 TRADING_EXECUTION_MODE）",
    )
    parser.add_argument(
        "--export-config",
        metavar="PATH",
        help="仅导出 scheduler 配置到指定文件然后退出",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings().trading
    risk_settings = get_settings().risk

    if args.export_config:
        target = Path(args.export_config)
        export_scheduler_config(target)
        print(f"Scheduler config exported to {target}")  # noqa: T201
        return

    session_ids = args.session or [settings.session_id]
    strategy_ids = args.strategy or [settings.strategy_id]
    if len(session_ids) != len(strategy_ids):
        raise ValueError("会话与策略数量必须一致")

    now = datetime.utcnow()
    configs = []
    symbols_input = args.symbols or settings.symbols
    if len(symbols_input) == 1 and isinstance(symbols_input[0], str) and "," in symbols_input[0]:
        symbols = [symbol.strip() for symbol in symbols_input[0].split(",") if symbol.strip()]
    else:
        symbols = symbols_input

    objective = args.objective or settings.objective
    interval = args.interval if args.interval is not None else settings.scheduler_interval_minutes
    lookback_days = args.lookback_days if args.lookback_days is not None else settings.lookback_days
    model = args.model or settings.llm_model
    llm_base_url = args.llm_base_url or settings.llm_base_url or None
    execution_mode = args.execution_mode or settings.execution_mode

    for session_id, strategy_id in zip(session_ids, strategy_ids):
        configs.append(
            TradingCycleConfig(
                session_id=session_id,
                strategy_id=strategy_id,
                symbols=symbols,
                objective=objective,
                history_start=now - timedelta(days=lookback_days),
                history_end=now,
                llm_model=model,
                llm_base_url=llm_base_url,
                freq=settings.freq,
                indicators=settings.indicators,
                initial_cash=settings.initial_cash,
                only_latest_bar=settings.only_latest_bar,
                symbol_universe_limit=settings.symbol_universe_limit,
                execution_mode=execution_mode,
            )
        )

    thresholds = RiskThresholds(
        max_equity_drawdown=risk_settings.max_equity_drawdown,
        max_position_ratio=risk_settings.max_position_ratio,
    )
    if args.max_drawdown is not None:
        thresholds.max_equity_drawdown = args.max_drawdown
    if args.max_position_ratio is not None:
        thresholds.max_position_ratio = args.max_position_ratio

    policy = RiskPolicy(thresholds)
    scheduler = start_managed_scheduler(configs, interval_minutes=interval, policy=policy)

    try:
        scheduler.print_jobs()
        while True:
            scheduler._event.wait(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
