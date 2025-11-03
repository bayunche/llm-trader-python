"""交易相关告警工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from llm_trader.monitoring import AlertEmitter


@dataclass
class TradingAlertService:
    emitter: AlertEmitter

    def risk_blocked(self, *, strategy_id: str, session_id: str, reason: str) -> None:
        self.emitter.emit(
            "风控阻断交易",
            details={"strategy_id": strategy_id, "session_id": session_id, "reason": reason},
        )

    def pipeline_stage_failed(self, stage: str, error: str) -> None:
        self.emitter.emit(
            "自动化阶段失败",
            details={"stage": stage, "error": error},
        )


__all__ = ["TradingAlertService"]
