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
    _seed(tmp_path)

    orders = data.get_orders("strategy-ai", "session-1")
    trades = data.get_trades("strategy-ai", "session-1")
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
