"""策略版本管理与持久化。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from llm_trader.common import get_logger
from llm_trader.common.paths import data_store_dir

_LOGGER = get_logger("strategy.repository")


@dataclass
class StrategyVersion:
    strategy_id: str
    version_id: str
    run_id: str
    created_at: datetime
    rules: List[Dict[str, object]]
    metrics: Dict[str, float]


class StrategyRepository:
    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or data_store_dir("strategies", "metadata")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.base_dir / "strategy_versions.jsonl"

    def register_version(self, version: StrategyVersion) -> Path:
        record = {
            "strategy_id": version.strategy_id,
            "version_id": version.version_id,
            "run_id": version.run_id,
            "created_at": version.created_at.isoformat(),
            "rules": version.rules,
            "metrics": version.metrics,
        }
        with self.metadata_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _LOGGER.info(
            "策略版本已登记",
            extra={
                "strategy_id": version.strategy_id,
                "version_id": version.version_id,
                "run_id": version.run_id,
            },
        )
        return self.metadata_path

    def list_versions(self, strategy_id: Optional[str] = None) -> List[StrategyVersion]:
        if not self.metadata_path.exists():
            return []
        versions: List[StrategyVersion] = []
        with self.metadata_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if strategy_id and data["strategy_id"] != strategy_id:
                    continue
                versions.append(
                    StrategyVersion(
                        strategy_id=data["strategy_id"],
                        version_id=data["version_id"],
                        run_id=data["run_id"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                        rules=data["rules"],
                        metrics=data["metrics"],
                    )
                )
        return versions
