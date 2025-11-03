"""全流程管线控制器测试。"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_full_pipeline import (
    PipelineController,
    STATUS_FILENAME,
)
from llm_trader.config import get_settings
from llm_trader.pipeline.auto import AutoTradingResult


def _status_path(base_dir: Path) -> Path:
    return base_dir / STATUS_FILENAME


def _reset_settings_cache() -> None:
    get_settings.cache_clear()


def test_pipeline_controller_success(tmp_path, monkeypatch) -> None:
    report_dir = tmp_path / "reports"
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(report_dir))
    monkeypatch.setenv("TRADING_EXECUTION_MODE", "sandbox")
    _reset_settings_cache()
    monkeypatch.addfinalizer(_reset_settings_cache)

    monkeypatch.setattr("scripts.run_full_pipeline._sync_data", lambda _repo: None)

    auto_result = AutoTradingResult(
        status="executed",
        backtest_metrics={"total_return": 0.12},
        managed_result=None,
        report_paths={"json": report_dir / "report.json"},
    )
    monkeypatch.setattr("scripts.run_full_pipeline.run_full_automation", lambda _cfg: auto_result)

    controller = PipelineController(status_dir=report_dir)
    status = controller.run()

    status_file = _status_path(report_dir)
    assert status_file.exists()

    payload = json.loads(status_file.read_text(encoding="utf-8"))
    stage_names = [stage["name"] for stage in payload["stages"]]
    assert status.execution_mode == "sandbox"
    assert "data_sync" in stage_names
    assert "report_generation" in stage_names


def test_pipeline_controller_live_mode_runs_with_warning(tmp_path, monkeypatch) -> None:
    report_dir = tmp_path / "reports"
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(report_dir))
    monkeypatch.setenv("TRADING_EXECUTION_MODE", "live")
    _reset_settings_cache()
    monkeypatch.addfinalizer(_reset_settings_cache)

    monkeypatch.setattr("scripts.run_full_pipeline._sync_data", lambda _repo: None)
    auto_result = AutoTradingResult(
        status="executed",
        backtest_metrics={},
        managed_result=None,
        report_paths=None,
    )
    monkeypatch.setattr("scripts.run_full_pipeline.run_full_automation", lambda _cfg: auto_result)

    controller = PipelineController(status_dir=report_dir)
    status = controller.run()

    payload = json.loads(_status_path(report_dir).read_text(encoding="utf-8"))
    preflight = payload["stages"][0]
    assert preflight["status"] == "success"
    assert status.blocked is False
    assert any("mock" in warn for warn in payload.get("warnings", []))


def test_pipeline_controller_records_sync_failure(tmp_path, monkeypatch) -> None:
    report_dir = tmp_path / "reports"
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(report_dir))
    monkeypatch.setenv("TRADING_EXECUTION_MODE", "sandbox")
    _reset_settings_cache()
    monkeypatch.addfinalizer(_reset_settings_cache)

    def _failing_sync(_repo):
        raise RuntimeError("sync boom")

    monkeypatch.setattr("scripts.run_full_pipeline._sync_data", _failing_sync)
    auto_result = AutoTradingResult(
        status="executed",
        backtest_metrics={},
        managed_result=None,
        report_paths=None,
    )
    monkeypatch.setattr("scripts.run_full_pipeline.run_full_automation", lambda _cfg: auto_result)

    controller = PipelineController(status_dir=report_dir)
    status = controller.run()

    payload = json.loads(_status_path(report_dir).read_text(encoding="utf-8"))
    assert status.failed is True
    assert any(stage["status"] == "failed" for stage in payload["stages"])


def test_pipeline_controller_emits_alert_on_failure(tmp_path, monkeypatch) -> None:
    report_dir = tmp_path / "reports"
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(report_dir))
    monkeypatch.setenv("TRADING_EXECUTION_MODE", "sandbox")
    _reset_settings_cache()
    monkeypatch.addfinalizer(_reset_settings_cache)

    monkeypatch.setattr("scripts.run_full_pipeline._sync_data", lambda _repo: None)

    class FakeAlert:
        def __init__(self, channel) -> None:
            self.calls = []

        def emit(self, message, *, details=None):
            self.calls.append((message, details))

    fake_alert = FakeAlert("log")
    monkeypatch.setattr("scripts.run_full_pipeline.AlertEmitter", lambda channel: fake_alert)

    def _failing_run(_cfg):
        raise RuntimeError("auto boom")

    monkeypatch.setattr("scripts.run_full_pipeline.run_full_automation", _failing_run)

    controller = PipelineController(status_dir=report_dir)
    controller.run()

    assert fake_alert.calls
    message, details = fake_alert.calls[0]
    assert "自动交易执行失败" in message
    assert details["error"] == "auto boom"
