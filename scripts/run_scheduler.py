#!/usr/bin/env python3
"""启动通用调度器。"""

from __future__ import annotations

import argparse
import time

from llm_trader.scheduler import load_scheduler_config, start_scheduler_from_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run configured scheduler")
    parser.add_argument("config", help="scheduler 配置 JSON 文件路径")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = load_scheduler_config(args.config)
    scheduler = start_scheduler_from_config(config)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
