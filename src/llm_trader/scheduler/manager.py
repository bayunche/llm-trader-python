"""调度管理器。"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from apscheduler.schedulers.background import BackgroundScheduler


@dataclass
class JobConfig:
    id: str
    callable_path: str
    trigger: str = "interval"
    interval_minutes: int = 60
    interval_seconds: int | None = None
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchedulerConfig:
    timezone: Optional[str] = None
    jobs: Iterable[JobConfig] = field(default_factory=list)


def load_scheduler_config(path: Path | str) -> SchedulerConfig:
    with Path(path).open("r", encoding="utf-8") as fp:
        raw = json.load(fp)
    jobs = [JobConfig(**item) for item in raw.get("jobs", [])]
    return SchedulerConfig(timezone=raw.get("timezone"), jobs=jobs)


def start_scheduler_from_dict(data: Dict[str, Any]) -> BackgroundScheduler:
    config = SchedulerConfig(
        timezone=data.get("timezone"),
        jobs=[JobConfig(**item) for item in data.get("jobs", [])],
    )
    return start_scheduler_from_config(config)


def start_scheduler_from_config(config: SchedulerConfig) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=config.timezone)
    for job_cfg in config.jobs:
        func = _resolve_callable(job_cfg.callable_path)
        if job_cfg.trigger == "interval":
            seconds = job_cfg.interval_seconds or 0
            minutes = job_cfg.interval_minutes if job_cfg.interval_seconds is None else 0
            scheduler.add_job(
                func,
                "interval",
                minutes=minutes,
                seconds=seconds,
                id=job_cfg.id,
                kwargs=job_cfg.kwargs,
            )
        elif job_cfg.trigger == "date":
            scheduler.add_job(
                func,
                "date",
                run_date=datetime.utcnow(),
                id=job_cfg.id,
                kwargs=job_cfg.kwargs,
            )
        else:  # pragma: no cover - 仅在配置错误时触发
            raise ValueError(f"Unsupported trigger: {job_cfg.trigger}")
    scheduler.start()
    return scheduler


def _resolve_callable(path: str):
    module_name, attr = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


__all__ = [
    "JobConfig",
    "SchedulerConfig",
    "load_scheduler_config",
    "start_scheduler_from_config",
    "start_scheduler_from_dict",
]
