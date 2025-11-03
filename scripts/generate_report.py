#!/usr/bin/env python3
"""生成策略报告脚本。"""

from __future__ import annotations

import argparse
from datetime import datetime

from llm_trader.reports import ReportBuilder, ReportPayload, ReportWriter
from llm_trader.reports.loader import load_report_payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate strategy report")
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--output", default="reports")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    data = load_report_payload(args.strategy, args.session)
    payload = ReportPayload(
        generated_at=datetime.utcnow(),
        metadata={
            "strategy_id": args.strategy,
            "session_id": args.session,
            "backtest_metrics": {},
        },
        equity_curve=data.get("equity", []),
        trades=data.get("trades", []),
        orders=data.get("orders", []),
        llm_logs=data.get("logs", []),
    )
    builder = ReportBuilder()
    result = builder.build(payload)
    writer = ReportWriter(args.output)
    files = writer.write(result)
    print("Report generated:")
    for name, path in files.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
