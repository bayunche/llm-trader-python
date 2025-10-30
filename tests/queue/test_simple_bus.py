"""简单事件总线测试。"""

from __future__ import annotations

import time

from llm_trader.queue import SimpleEventBus


def test_simple_event_bus() -> None:
    bus = SimpleEventBus()
    results = []

    bus.subscribe("trade", lambda payload: results.append(payload["id"]))
    bus.start()
    bus.publish("trade", {"id": 1})
    time.sleep(0.1)
    bus.stop()

    assert results == [1]
