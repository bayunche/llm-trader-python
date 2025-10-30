"""策略评估与版本管理工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

from llm_trader.strategy.generator import StrategyCandidate
from llm_trader.strategy.repository import StrategyRepository, StrategyVersion


@dataclass
class EvaluationResult:
    strategy_id: str
    version_id: str
    selected: StrategyCandidate


def select_and_register_best(
    strategy_id: str,
    candidates: List[StrategyCandidate],
    repository: StrategyRepository,
    *,
    sort_metric: str = "annual_return",
) -> EvaluationResult:
    if not candidates:
        raise ValueError("候选策略为空，无法评估")

    sorted_candidates = sorted(candidates, key=lambda c: c.metrics.get(sort_metric, 0.0), reverse=True)
    selected = sorted_candidates[0]
    version_id = f"v-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:6]}"
    repository.register_version(
        StrategyVersion(
            strategy_id=strategy_id,
            version_id=version_id,
            run_id=selected.metrics.get("run_id", version_id),
            created_at=datetime.utcnow(),
            rules=[rule.__dict__ for rule in selected.rules],
            metrics=selected.metrics,
        )
    )
    return EvaluationResult(strategy_id=strategy_id, version_id=version_id, selected=selected)
