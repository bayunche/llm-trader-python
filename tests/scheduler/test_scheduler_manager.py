"""调度管理器测试。"""

from __future__ import annotations

import time

from llm_trader.scheduler import start_scheduler_from_dict
from tests.scheduler import stubs


def test_scheduler_runs_jobs(monkeypatch) -> None:
    stubs.EVENTS = []
    config = {
        "jobs": [
            {
                "id": "stub",
                "callable_path": "tests.scheduler.stubs.record_job",
                "trigger": "interval",
                "interval_seconds": 1,
                "kwargs": {"value": 1},
            }
        ]
    }
    scheduler = start_scheduler_from_dict(config)
    time.sleep(1.5)
    scheduler.shutdown()
    assert stubs.EVENTS == [{"value": 1}]
