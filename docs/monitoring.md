# 监控与告警

> 更新时间：2025-10-30 ｜ 执行者：Codex

- `llm_trader.monitoring.AlertEmitter` 支持多种告警输出，默认写入日志，可切换至 `stdout` 用于管道输出。
- 通过 `AlertEmitter(channel="stdout").emit("风险告警", details={"strategy": "demo"})` 可将 JSON 格式告警写入标准输出并由外部采集。
- 安全起见，风控模块的所有告警统一使用 `monitoring.alert` 日志标识符，便于接入第三方日志平台或告警系统。
