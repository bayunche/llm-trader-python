#!/usr/bin/env python3
"""运行从数据同步到报表生成的完整自动化流程。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from llm_trader.common import get_logger
from llm_trader.config import get_settings
from llm_trader.data.pipelines.realtime_quotes import RealtimeQuotesPipeline
from llm_trader.data.pipelines.symbols import SymbolsPipeline
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.pipeline.auto import AutoTradingConfig, AutoTradingResult, BacktestCriteria, run_full_automation
from llm_trader.trading.orchestrator import TradingCycleConfig
from llm_trader.monitoring import AlertEmitter

LOGGER = get_logger("scripts.full_pipeline")
STATUS_FILENAME = "status.json"


def _sync_data(repository: ParquetRepository) -> None:
    """执行数据同步阶段。"""

    settings = get_settings().trading
    LOGGER.info("开始同步证券主表")
    SymbolsPipeline(repository=repository).sync()
    LOGGER.info("开始同步实时行情")
    RealtimeQuotesPipeline(repository=repository, symbols_limit=settings.symbol_universe_limit).sync(
        settings.symbols or None
    )


def _build_auto_config() -> AutoTradingConfig:
    """构建自动交易配置。"""

    settings = get_settings().trading
    now = datetime.utcnow()
    history_start = now - timedelta(days=settings.lookback_days)
    trading_cfg = TradingCycleConfig(
        session_id=settings.session_id,
        strategy_id=settings.strategy_id,
        symbols=settings.symbols,
        objective=settings.objective,
        indicators=tuple(settings.indicators),
        freq=settings.freq,
        history_start=history_start,
        history_end=now,
        initial_cash=settings.initial_cash,
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url or None,
        only_latest_bar=settings.only_latest_bar,
        symbol_universe_limit=settings.symbol_universe_limit,
        execution_mode=settings.execution_mode,
    )
    criteria = BacktestCriteria(
        min_total_return=settings.backtest_min_return,
        max_drawdown=settings.backtest_max_drawdown,
    )
    return AutoTradingConfig(
        trading=trading_cfg,
        backtest_start=history_start,
        backtest_end=now,
        criteria=criteria,
        run_backtest=settings.run_backtest,
    )


@dataclass
class StageRecord:
    """记录单个阶段的执行结果。"""

    name: str
    status: str
    detail: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class PipelineStatus:
    """用于向 Dashboard 暴露执行状态。"""

    execution_mode: str
    stages: List[StageRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, object]:
        return {
            "execution_mode": self.execution_mode,
            "warnings": self.warnings,
            "stages": [asdict(stage) for stage in self.stages],
            "updated_at": self.updated_at,
        }

    @property
    def blocked(self) -> bool:
        return any(stage.status == "blocked" for stage in self.stages)

    @property
    def failed(self) -> bool:
        return any(stage.status == "failed" for stage in self.stages)


class PipelineController:
    """封装全流程执行与状态写入。"""

    def __init__(
        self,
        *,
        repository: Optional[ParquetRepository] = None,
        status_dir: Optional[Path] = None,
        status_filename: str = STATUS_FILENAME,
    ) -> None:
        self._settings = get_settings()
        self._repository = repository or ParquetRepository()
        base_dir = Path(status_dir or self._settings.trading.report_output_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        self._status_path = base_dir / status_filename
        self._status = PipelineStatus(execution_mode=self._settings.trading.execution_mode)
        self._alert = AlertEmitter(channel=self._settings.monitoring.channel)

    def run(self) -> PipelineStatus:
        """执行全流程并返回状态快照。"""

        LOGGER.info(
            "启动全流程控制器",
            extra={"execution_mode": self._status.execution_mode, "status_path": str(self._status_path)},
        )
        self._run_preflight()
        if self._status.blocked or self._status.failed:
            return self._status

        self._run_data_sync()
        if self._status.failed:
            return self._status

        self._run_auto_trading()
        return self._status

    def _run_preflight(self) -> None:
        started = self._now()
        if self._status.execution_mode == "live":
            provider = self._settings.trading.broker_provider or ""
            if provider.lower() == "mock":
                detail = "live 模式启用 mock 券商，仅模拟真实执行"
                self._status.warnings.append(detail)
            else:
                detail = f"live 模式使用券商提供方：{provider}"
            self._add_stage("preflight", "success", detail, started)
            LOGGER.info(detail)
        else:
            self._add_stage("preflight", "success", "已启用 sandbox 模式", started)

    def _run_data_sync(self) -> None:
        started = self._now()
        try:
            _sync_data(self._repository)
        except Exception as exc:  # pragma: no cover - 异常路径留给冒烟验证
            LOGGER.exception("数据同步失败", extra={"error": str(exc)})
            self._add_stage("data_sync", "failed", str(exc), started)
            self._alert.emit("数据同步失败", details={"error": str(exc)})
            return

        self._add_stage("data_sync", "success", "证券主表与实时行情同步完成", started)

    def _run_auto_trading(self) -> None:
        auto_cfg = _build_auto_config()
        LOGGER.info(
            "启动自动交易流程",
            extra={
                "strategy_id": auto_cfg.trading.strategy_id,
                "session_id": auto_cfg.trading.session_id,
                "execution_mode": auto_cfg.trading.execution_mode,
            },
        )
        started = self._now()
        try:
            result = run_full_automation(auto_cfg)
        except Exception as exc:  # pragma: no cover - 异常路径留给冒烟验证
            LOGGER.exception("自动交易执行失败", extra={"error": str(exc)})
            self._add_stage("auto_trading", "failed", str(exc), started)
            self._alert.emit("自动交易执行失败", details={"error": str(exc)})
            return

        stage_status = self._map_result_status(result.status)
        detail_parts: List[str] = [f"status={result.status}"]
        if result.backtest_metrics:
            metrics = ", ".join(f"{k}={v}" for k, v in result.backtest_metrics.items())
            detail_parts.append(f"backtest[{metrics}]")
        if result.managed_result and result.managed_result.decision.alerts:
            alerts = ", ".join(result.managed_result.decision.alerts)
            detail_parts.append(f"alerts[{alerts}]")

        self._add_stage("auto_trading", stage_status, "; ".join(detail_parts), started)
        self._record_report_stage(result)

    def _record_report_stage(self, result: AutoTradingResult) -> None:
        started = self._now()
        if result.report_paths:
            rendered = ", ".join(f"{name}={path}" for name, path in result.report_paths.items())
            self._add_stage("report_generation", "success", f"生成报表：{rendered}", started)
            return

        detail = "未生成报表，请核对数据输入或执行模式"
        if detail not in self._status.warnings:
            self._status.warnings.append(detail)
        self._add_stage("report_generation", "skipped", detail, started)

    def _add_stage(
        self,
        name: str,
        status: str,
        detail: Optional[str],
        started_at: Optional[str],
    ) -> None:
        record = StageRecord(
            name=name,
            status=status,
            detail=detail,
            started_at=started_at,
            finished_at=self._now(),
        )
        self._status.stages.append(record)
        self._write_status()

    def _write_status(self) -> None:
        self._status.updated_at = self._now()
        payload = self._status.to_dict()
        with self._status_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

    @staticmethod
    def _map_result_status(status: str) -> str:
        if status == "executed":
            return "success"
        if status == "risk_blocked":
            return "blocked"
        return "failed"

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()


def main() -> None:
    """脚本入口。"""

    controller = PipelineController()
    status = controller.run()
    status_file_path = Path(get_settings().trading.report_output_dir) / STATUS_FILENAME
    LOGGER.info(
        "自动交易流程结束",
        extra={
            "blocked": status.blocked,
            "failed": status.failed,
            "status_file": str(status_file_path),
            "warnings": status.warnings,
        },
    )


if __name__ == "__main__":
    main()


__all__ = ["PipelineController", "PipelineStatus", "StageRecord", "STATUS_FILENAME", "main"]
