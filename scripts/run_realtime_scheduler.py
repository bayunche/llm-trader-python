#!/usr/bin/env python3
"""启动实时行情调度脚本。"""

from __future__ import annotations

import argparse
import time
from typing import List

from llm_trader.tasks.realtime import start_scheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start realtime quotes scheduler")
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="证券代码列表，例如 600000.SH 000001.SZ；未提供时自动使用证券主表中的全部标的",
    )
    parser.add_argument("--interval", type=int, default=1, help="调度间隔（分钟）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scheduler = start_scheduler(args.symbols, interval_minutes=args.interval)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
