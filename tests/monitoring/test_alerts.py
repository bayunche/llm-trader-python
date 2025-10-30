"""告警发射测试。"""

from __future__ import annotations

import json
from io import StringIO
import sys

from llm_trader.monitoring import AlertEmitter


def test_alert_emitter_stdout(monkeypatch) -> None:
    buffer = StringIO()
    monkeypatch.setattr(sys, "stdout", buffer)
    emitter = AlertEmitter(channel="stdout")
    emitter.emit("test", details={"k": 1})
    output = json.loads(buffer.getvalue())
    assert output["message"] == "test"
    assert output["details"]["k"] == 1
