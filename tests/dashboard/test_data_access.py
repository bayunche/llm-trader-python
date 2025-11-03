"""仪表盘数据访问测试。"""

from __future__ import annotations

import json
from datetime import datetime

from llm_trader.data import default_manager
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.strategy import LLMStrategyLogRepository, StrategyRepository, StrategyVersion
from dashboard import data


def _seed(tmp_path) -> None:
    manager = default_manager(base_dir=tmp_path / "data_store")
    repo = ParquetRepository(manager=manager)
    dt = datetime(2024, 1, 2, 9, 30)
    repo.write_trading_orders(
        "session-1",
        "strategy-ai",
        dt,
        [
            {
                "order_id": "o-1",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.0,
                "status": "filled",
                "filled_volume": 100,
                "filled_amount": 1000.0,
                "created_at": dt,
            }
        ],
    )
    repo.write_trading_trades(
        "session-1",
        "strategy-ai",
        dt,
        [
            {
                "trade_id": "t-1",
                "order_id": "o-1",
                "symbol": "600000.SH",
                "side": "buy",
                "volume": 100,
                "price": 10.0,
                "fee": 5.0,
                "tax": 0.0,
                "timestamp": dt,
            }
        ],
    )
    repo.write_trading_equity(
        "session-1",
        "strategy-ai",
        {
            "timestamp": dt,
            "cash": 99900.0,
            "equity": 100500.0,
            "positions": json.dumps([{"symbol": "600000.SH", "volume": 100}]),
        },
    )
    repo_meta = StrategyRepository()
    repo_meta.register_version(
        StrategyVersion(
            strategy_id="strategy-ai",
            version_id="v1",
            run_id="run1",
            created_at=dt,
            rules=[],
            metrics={"total_return": 0.1},
        )
    )
    logger = LLMStrategyLogRepository(manager=manager)
    logger.append(
        strategy_id="strategy-ai",
        session_id="session-1",
        prompt="prompt",
        response="response",
        payload={"objective": "test"},
        timestamp=dt,
    )


def test_data_access(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    data.invalidate_cache()
    _seed(tmp_path)

    orders = data.get_orders("strategy-ai", "session-1", limit=1)
    trades = data.get_trades("strategy-ai", "session-1", limit=1)
    equity = data.get_equity_curve("strategy-ai", "session-1")
    logs = data.get_llm_logs("strategy-ai", "session-1")
    strategies = data.list_strategy_ids()
    sessions = data.list_strategy_sessions()
    versions = data.list_strategy_versions("strategy-ai")

    assert orders[0]["order_id"] == "o-1"
    assert trades[0]["trade_id"] == "t-1"
    assert equity[0]["equity"] == 100500.0
    assert logs[0]["objective"] == "test"
    assert "strategy-ai" in strategies
    assert {"strategy_id": "strategy-ai", "session_id": "session-1"} in sessions
    assert versions and versions[0].version_id == "v1"
    assert data.count_orders("strategy-ai", "session-1") == 1
    assert data.count_trades("strategy-ai", "session-1") == 1
    assert data.count_equity_points("strategy-ai", "session-1") >= 1
    assert data.count_llm_logs("strategy-ai", "session-1") == 1


def test_load_pipeline_status_success(tmp_path, monkeypatch) -> None:
    status_dir = tmp_path / "reports"
    status_dir.mkdir(parents=True)
    status_file = status_dir / "status.json"
    payload = {
        "execution_mode": "sandbox",
        "warnings": [],
        "stages": [{"name": "preflight", "status": "success"}],
        "updated_at": "2024-01-01T00:00:00",
    }
    status_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("LLM_TRADER_PIPELINE_STATUS", str(status_file))

    info = data.load_pipeline_status()
    assert info["available"] is True
    assert info["data"]["execution_mode"] == "sandbox"


def test_load_pipeline_status_missing(tmp_path, monkeypatch) -> None:
    status_dir = tmp_path / "reports"
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(status_dir))
    monkeypatch.delenv("LLM_TRADER_PIPELINE_STATUS", raising=False)

    info = data.load_pipeline_status()
    assert info["available"] is False
    assert "不存在" in info["error"]


def test_prompt_template_crud(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_STORE_DIR", str(tmp_path / "data_store"))
    data.invalidate_cache()
    # 确保默认模板可列出
    templates = data.list_prompt_templates()
    assert "strategy" in templates

    saved = data.save_prompt_template("strategy", "测试模板：{objective}")
    assert saved["source"] == "custom"
    assert saved["scenario"] == "default"
    assert "测试模板" in saved["content"]

    loaded = data.load_prompt_template("strategy")
    assert loaded["content"] == "测试模板：{objective}"
    assert loaded["source"] == "custom"
    versions = data.list_prompt_template_versions("strategy")
    assert versions
    restored = data.restore_prompt_template_version("strategy", versions[0]["version_id"])
    assert restored["content"] == saved["content"]

    reset = data.reset_prompt_template("strategy")
    assert reset["source"] == "default"
