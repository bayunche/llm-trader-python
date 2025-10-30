"""策略版本仓库测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.strategy.repository import StrategyRepository, StrategyVersion


def test_strategy_repository_register_and_list(tmp_path) -> None:
    repo = StrategyRepository(base_dir=tmp_path)
    version = StrategyVersion(
        strategy_id="demo",
        version_id="v1",
        run_id="run1",
        created_at=datetime(2024, 7, 1),
        rules=[{"indicator": "sma", "column": "close", "params": {"window": 3}, "operator": ">", "threshold": 10.5}],
        metrics={"annual_return": 0.12},
    )
    path = repo.register_version(version)
    assert path.exists()

    versions = repo.list_versions("demo")
    assert len(versions) == 1
    assert versions[0].version_id == "v1"
