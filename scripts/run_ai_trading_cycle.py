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

from llm_trader.trading import TradingCycleConfig, run_ai_trading_cycle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI-powered trading cycle")
    parser.add_argument("--session", required=True, help="交易会话 ID")
    parser.add_argument("--strategy", required=True, help="策略 ID")
    parser.add_argument("--symbols", nargs="+", required=True, help="标的列表，如 600000.SH")
    parser.add_argument("--objective", required=True, help="策略目标描述")
    parser.add_argument("--indicators", nargs="+", default=["sma", "ema"], help="候选技术指标")
    parser.add_argument("--freq", default="D", help="历史行情频率，默认 D")
    parser.add_argument("--lookback-days", type=int, default=120, help="历史回看天数")
    parser.add_argument("--initial-cash", type=float, default=1_000_000.0, help="初始资金")
    parser.add_argument("--model", default="gpt-4.1-mini", help="大模型名称")
    parser.add_argument("--no-only-latest", action="store_true", help="执行所有历史 bar 的信号")
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

    result = run_ai_trading_cycle(config)
    summary = {
        "session": args.session,
        "strategy": args.strategy,
        "orders_executed": result["orders_executed"],
        "trades_filled": result["trades_filled"],
        "suggestion": result["suggestion"].description,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
