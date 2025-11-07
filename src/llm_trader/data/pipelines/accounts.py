from __future__ import annotations

"""
账户资金与持仓采集管道。

默认实现基于配置回退，后续可替换为真实券商适配器或账户服务。
"""

from datetime import datetime
from typing import Callable, Dict, Optional

from llm_trader.config import get_settings
from llm_trader.db.models.enums import RiskPosture

SnapshotProvider = Callable[[], Dict[str, object]]


class AccountSnapshotPipeline:
    """包装账户快照采集逻辑，返回标准化字典。"""

    def __init__(self, provider: Optional[SnapshotProvider] = None) -> None:
        self._provider = provider

    def fetch(self) -> Dict[str, object]:
        """采集账户资金与持仓信息并返回标准化结构。"""

        raw = self._provider() if self._provider else self._default_payload()
        captured_at = raw.get("captured_at")
        if isinstance(captured_at, str):
            try:
                captured_at = datetime.fromisoformat(captured_at)
            except ValueError:  # pragma: no cover - 非标准格式回退
                captured_at = datetime.utcnow()
        elif not isinstance(captured_at, datetime):
            captured_at = datetime.utcnow()

        posture = raw.get("posture", RiskPosture.NORMAL)
        if not isinstance(posture, RiskPosture):
            posture = RiskPosture(str(posture))

        positions = raw.get("positions") or []
        return {
            "captured_at": captured_at,
            "nav": raw.get("nav"),
            "cash": raw.get("cash"),
            "available": raw.get("available"),
            "posture": posture,
            "positions": positions,
        }

    @staticmethod
    def _default_payload() -> Dict[str, object]:
        """当未提供 provider 时的默认占位实现。"""

        trading = get_settings().trading
        return {
            "captured_at": datetime.utcnow(),
            "nav": trading.initial_cash,
            "cash": trading.initial_cash,
            "available": trading.initial_cash,
            "posture": RiskPosture.NORMAL,
            "positions": [],
        }


__all__ = ["AccountSnapshotPipeline"]
