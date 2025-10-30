"""实时调度测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from llm_trader.tasks.realtime import fetch_realtime_quotes, start_scheduler


@patch("llm_trader.tasks.realtime.RealtimeQuotesPipeline")
def test_fetch_realtime_quotes(mock_pipeline_cls: MagicMock) -> None:
    pipeline = mock_pipeline_cls.return_value
    pipeline.sync.return_value = ["record"]
    fetch_realtime_quotes(["600000.SH"])
    pipeline.sync.assert_called_once()


@patch("llm_trader.tasks.realtime.BackgroundScheduler")
def test_start_scheduler(mock_scheduler_cls: MagicMock) -> None:
    scheduler = mock_scheduler_cls.return_value
    scheduler.add_job.return_value = None
    result = start_scheduler(["600000.SH"], interval_minutes=5)
    scheduler.add_job.assert_called_once()
    scheduler.start.assert_called_once()
    assert result is scheduler
