#!/usr/bin/env python3
"""命令行入口：运行一次 AI 自动交易循环。

示例：

```
python scripts/run_ai_trading_cycle.py \
  --session session-demo \
  --strategy strategy-demo \
  --symbols 600000.SH 000001.SZ \
  --objective "获取稳健收益" \
  --indicators sma ema rsi \
  --lookback-days 120
```

OpenAI 兼容接口所需的 `OPENAI_API_KEY` 或者 `LLM_TRADER_API_KEY` 等信息请通过环境变量提供。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta

from llm_trader.config import get_settings
from llm_trader.trading import TradingCycleConfig, run_ai_trading_cycle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI-powered trading cycle")
    parser.add_argument("--session", help="交易会话 ID")
    parser.add_argument("--strategy", help="策略 ID")
    parser.add_argument("--symbols", nargs="+", help="标的列表，如 600000.SH")
    parser.add_argument("--objective", help="策略目标描述")
    parser.add_argument("--indicators", nargs="+", default=None, help="候选技术指标")
    parser.add_argument("--freq", default=None, help="历史行情频率，默认使用 TRADING_FREQ")
    parser.add_argument("--lookback-days", type=int, default=None, help="历史回看天数")
    parser.add_argument("--initial-cash", type=float, default=None, help="初始资金")
    parser.add_argument("--model", default=None, help="大模型名称")
    parser.add_argument("--llm-base-url", default=None, help="OpenAI 兼容接口的 Base URL")
    parser.add_argument("--no-only-latest", action="store_true", help="执行所有历史 bar 的信号")
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

    result = run_ai_trading_cycle(config)
    summary = {
        "session": session_id,
        "strategy": strategy_id,
        "orders_executed": result["orders_executed"],
        "trades_filled": result["trades_filled"],
        "suggestion": result["suggestion"].description,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
