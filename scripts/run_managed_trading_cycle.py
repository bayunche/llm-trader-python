#!/usr/bin/env python3
"""执行带风控策略的 AI 交易循环。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta

from llm_trader.config import get_settings
from llm_trader.trading import TradingCycleConfig, RiskPolicy, RiskThresholds
from llm_trader.trading.manager import run_managed_trading_cycle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run managed AI trading cycle")
    parser.add_argument("--session")
    parser.add_argument("--strategy")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--objective")
    parser.add_argument("--indicators", nargs="+", default=None)
    parser.add_argument("--freq", default=None)
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--initial-cash", type=float, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--llm-base-url", default=None, help="OpenAI 兼容接口的 Base URL")
    parser.add_argument("--max-drawdown", type=float, default=None, help="最大回撤阈值，例如 0.1")
    parser.add_argument("--max-position-ratio", type=float, default=None, help="单标的最大仓位占比，例如 0.3")
    parser.add_argument("--no-only-latest", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = get_settings().trading
    session_id = args.session or settings.session_id
    strategy_id = args.strategy or settings.strategy_id
    symbols = args.symbols or settings.symbols
    objective = args.objective or settings.objective
    indicators = args.indicators or settings.indicators
    freq = args.freq or settings.freq
    lookback_days = args.lookback_days if args.lookback_days is not None else settings.lookback_days
    initial_cash = args.initial_cash if args.initial_cash is not None else settings.initial_cash
    model = args.model or settings.llm_model
    llm_base_url = args.llm_base_url or settings.llm_base_url or None
    only_latest = settings.only_latest_bar
    if args.no_only_latest:
        only_latest = False

    if not symbols:
        raise SystemExit("未指定交易标的，请通过 --symbols 或 TRADING_SYMBOLS 配置")

    history_end = datetime.utcnow()
    history_start = history_end - timedelta(days=lookback_days)

    config = TradingCycleConfig(
        session_id=session_id,
        strategy_id=strategy_id,
        symbols=symbols,
        objective=objective,
        indicators=indicators,
        freq=freq,
        history_start=history_start,
        history_end=history_end,
        initial_cash=initial_cash,
        llm_model=model,
        llm_base_url=llm_base_url,
        only_latest_bar=only_latest,
        symbol_universe_limit=settings.symbol_universe_limit,
    )

    risk_settings = get_settings().risk
    thresholds = RiskThresholds(
        max_equity_drawdown=risk_settings.max_equity_drawdown,
        max_position_ratio=risk_settings.max_position_ratio,
    )
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
