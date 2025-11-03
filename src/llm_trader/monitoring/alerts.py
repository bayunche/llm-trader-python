"""告警发布器实现。"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import Dict, Optional


class AlertChannel:
    LOG = "log"
    STDOUT = "stdout"
    STDERR = "stderr"


@dataclass
class AlertEmitter:
    """将告警发布到不同渠道。"""

    channel: str = AlertChannel.LOG

    def emit(self, message: str, *, details: Optional[Dict[str, object]] = None) -> None:
        payload = {"message": message, "details": details or {}}
        if self.channel == AlertChannel.LOG:
            logging.getLogger("monitoring.alert").warning(message, extra=payload)
        elif self.channel == AlertChannel.STDOUT:
            print(json.dumps(payload, ensure_ascii=False))
        elif self.channel == AlertChannel.STDERR:  # pragma: no cover - rarely used
            print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        else:  # pragma: no cover - 扩展渠道
            logging.getLogger("monitoring.alert").error("Unsupported alert channel", extra=payload)


__all__ = ["AlertEmitter", "AlertChannel"]
