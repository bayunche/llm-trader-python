# 消息队列 / 事件总线

> 更新时间：2025-10-30 ｜ 执行者：Codex

- `SimpleEventBus` 提供轻量级事件发布/订阅能力，可在本地进程内模拟消息队列或作为外部系统适配器的占位实现。
- 使用示例：

```python
from llm_trader.queue import SimpleEventBus

bus = SimpleEventBus()
bus.subscribe("trade_completed", lambda payload: print("收到成交", payload))
bus.start()
bus.publish("trade_completed", {"id": "T001", "symbol": "600000.SH"})
bus.stop()
```

- 后续可以将该事件总线替换为 Redis、RabbitMQ 等，实现真正的分布式消息传递。
