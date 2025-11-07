#!/usr/bin/env python3
"""统一入口：启动调度器、执行首轮自动交易并运行仪表盘。"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from llm_trader.scheduler import export_scheduler_config, load_scheduler_config, start_scheduler_from_config


LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="[app] %(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger("llm_trader.app")


def _run_pipeline_once(report_dir: Path, status_filename: str) -> None:
    """执行一次完整流水线，允许失败但需记录状态文件路径。"""

    status_path = report_dir / status_filename
    status_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["REPORT_OUTPUT_DIR"] = str(report_dir)
    env["PIPELINE_STATUS_FILENAME"] = status_filename
    LOGGER.info("Running full pipeline once to warm up data…")
    try:
        subprocess.run(
            [sys.executable, "scripts/run_full_pipeline.py"],
            check=True,
            env=env,
        )
        LOGGER.info("Full pipeline completed successfully")
    except subprocess.CalledProcessError as exc:  # pragma: no cover - 失败时只记录日志
        LOGGER.warning("Full pipeline exited with code %s", exc.returncode)
    finally:
        if status_path.exists():
            os.environ["LLM_TRADER_PIPELINE_STATUS"] = str(status_path)
            LOGGER.info("Pipeline status recorded at %s", status_path)
        else:
            LOGGER.warning("Pipeline status file not found at %s", status_path)


def _start_scheduler(config_path: Path) -> Optional[object]:
    """启动调度器并返回实例，若配置缺失则返回 None。"""

    if not config_path.exists():
        LOGGER.info("Scheduler config %s not found，auto generating…", config_path)
        export_scheduler_config(config_path)
    scheduler_config = load_scheduler_config(config_path)
    scheduler = start_scheduler_from_config(scheduler_config)
    LOGGER.info("Scheduler started with config %s", config_path)
    return scheduler


def _spawn_streamlit(port: int) -> subprocess.Popen:
    """启动 Streamlit 仪表盘进程。"""

    cmd = [
        "streamlit",
        "run",
        "dashboard/app.py",
        "--server.address=0.0.0.0",
        f"--server.port={port}",
        "--server.headless=true",
    ]
    LOGGER.info("Starting Streamlit dashboard on port %d", port)
    return subprocess.Popen(cmd)


def main() -> None:
    report_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "reports"))
    status_filename = os.getenv("PIPELINE_STATUS_FILENAME", "status.json")
    scheduler_config_path = Path(os.getenv("LLM_TRADER_SCHEDULER_CONFIG", "config/scheduler.prod.json"))
    dashboard_port = int(os.getenv("DASHBOARD_PORT", "8501"))
    skip_initial_pipeline = os.getenv("LLM_TRADER_SKIP_INITIAL_PIPELINE", "0").lower() in {"1", "true", "yes"}

    scheduler = None
    streamlit_proc: Optional[subprocess.Popen] = None

    def shutdown(_signum: int, _frame) -> None:
        LOGGER.info("Received shutdown signal, stopping services…")
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if streamlit_proc and streamlit_proc.poll() is None:
            streamlit_proc.terminate()
            try:
                streamlit_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                streamlit_proc.kill()
        LOGGER.info("Shutdown complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if not skip_initial_pipeline:
        _run_pipeline_once(report_dir, status_filename)
    else:
        LOGGER.info("Skip initial pipeline as requested by environment variable")

    scheduler = _start_scheduler(scheduler_config_path)
    streamlit_proc = _spawn_streamlit(dashboard_port)

    try:
        while True:
            if streamlit_proc.poll() is not None:
                raise RuntimeError("Streamlit process exited unexpectedly")
            time.sleep(30)
    except Exception as exc:  # pragma: no cover - 主循环异常仅记录日志
        LOGGER.error("Main loop terminated: %s", exc)
        shutdown(0, None)


if __name__ == "__main__":
    main()
