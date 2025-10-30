"""大模型策略日志持久化。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from llm_trader.data import DatasetKind, DataStoreManager, default_manager


@dataclass
class LLMStrategyLogRepository:
    """负责记录 LLM 提示词与响应内容。"""

    manager: DataStoreManager = default_manager()

    def append(
        self,
        *,
        strategy_id: str,
        session_id: str,
        prompt: str,
        response: str,
        payload: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> None:
        ts = timestamp or datetime.utcnow()
        path = self.manager.path_for(
            DatasetKind.STRATEGY_LLM_LOGS,
            symbol=strategy_id,
            freq=session_id,
            timestamp=ts,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": ts.isoformat(),
            "prompt": prompt,
            "response": response,
            **payload,
        }
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")


__all__ = ["LLMStrategyLogRepository"]
