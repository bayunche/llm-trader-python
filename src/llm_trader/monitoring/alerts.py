"""告警输出。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class AlertEmitter:
    channel: str = "log"

    def emit(self, message: str, *, details: Optional[Dict[str, object]] = None) -> None:
        payload = {"message": message, "details": details or {}}
        if self.channel == "log":
            logging.getLogger("monitoring.alert").warning(message, extra=payload)
        elif self.channel == "stdout":
            print(json.dumps(payload, ensure_ascii=False))
        else:  # pragma: no cover - 扩展渠道
            logging.getLogger("monitoring.alert").error("Unsupported alert channel", extra=payload)


__all__ = ["AlertEmitter"]
