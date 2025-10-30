"""简单事件总线，用于队列/消息触发。"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class SimpleEventBus:
    handlers: Dict[str, List[Callable[[dict], None]]] = field(default_factory=dict)
    _queue: "queue.Queue[tuple[str, dict]]" = field(default_factory=queue.Queue, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)

    def subscribe(self, event: str, handler: Callable[[dict], None]) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def publish(self, event: str, payload: dict) -> None:
        self._queue.put((event, payload))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                event, payload = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            for handler in self.handlers.get(event, []):
                handler(payload)
            self._queue.task_done()


__all__ = ["SimpleEventBus"]
