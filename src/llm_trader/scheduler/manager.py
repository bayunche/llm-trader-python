"""调度管理器。"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from llm_trader.config import get_settings

if TYPE_CHECKING:
    from llm_trader.config.settings import AppSettings

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


def build_scheduler_config(settings: Optional["AppSettings"] = None) -> Dict[str, Any]:
    """根据当前配置生成调度 JSON 结构。"""

    app_settings = settings or get_settings()
    trading = app_settings.trading
    scheduler_settings = app_settings.scheduler
    interval = max(1, trading.scheduler_interval_minutes)

    quotes_kwargs: Dict[str, Any] = {}
    if trading.symbols:
        quotes_kwargs["symbols"] = trading.symbols

    config_payload: Dict[str, Any] = {
        "session_id": trading.session_id,
        "strategy_id": trading.strategy_id,
        "symbols": trading.symbols,
        "objective": trading.objective,
        "indicators": list(trading.indicators),
        "freq": trading.freq,
        "initial_cash": trading.initial_cash,
        "llm_model": trading.llm_model,
        "only_latest_bar": trading.only_latest_bar,
        "symbol_universe_limit": trading.symbol_universe_limit,
        "execution_mode": trading.execution_mode,
        "selection_metric": trading.selection_metric,
        "lookback_days": trading.lookback_days,
    }
    if trading.llm_base_url:
        config_payload["llm_base_url"] = trading.llm_base_url
    if trading.symbol_universe_limit is None:
        config_payload.pop("symbol_universe_limit", None)

    account_kwargs: Dict[str, Any] = {}
    if trading.symbol_universe_limit is not None:
        account_kwargs["symbol_universe_limit"] = trading.symbol_universe_limit

    jobs: List[Dict[str, Any]] = [
        {
            "id": "realtime-quotes",
            "callable_path": "llm_trader.tasks.realtime.fetch_realtime_quotes",
            "trigger": "interval",
            "interval_minutes": interval,
            "kwargs": quotes_kwargs,
        },
        {
            "id": "account-snapshot",
            "callable_path": "llm_trader.tasks.managed_cycle.sync_account_snapshot",
            "trigger": "interval",
            "interval_minutes": interval,
            "kwargs": account_kwargs,
        },
        {
            "id": "managed-trading",
            "callable_path": "llm_trader.tasks.managed_cycle.run_cycle",
            "trigger": "interval",
            "interval_minutes": interval,
            "kwargs": {"config": config_payload},
        },
    ]

    return {
        "timezone": scheduler_settings.timezone,
        "jobs": jobs,
    }


def export_scheduler_config(
    path: Path | str,
    *,
    settings: Optional["AppSettings"] = None,
    overwrite: bool = True,
) -> Dict[str, Any]:
    """将当前配置导出为 JSON 文件。"""

    payload = build_scheduler_config(settings)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and target.exists():
        raise FileExistsError(f"{target} already exists")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "JobConfig",
    "SchedulerConfig",
    "load_scheduler_config",
    "start_scheduler_from_config",
    "start_scheduler_from_dict",
    "build_scheduler_config",
    "export_scheduler_config",
]
