# 监控与告警

> 更新时间：2025-11-03 ｜ 执行者：Codex

## 告警渠道

- `llm_trader.monitoring.AlertEmitter` 提供 `log`、`stdout`、`stderr` 三种内置渠道，默认写入 `monitoring.alert` 日志；通过 `.env` 中的 `MONITORING_ALERT_CHANNEL` 可覆盖。
- 示例：
  ```python
  from llm_trader.monitoring import AlertEmitter

  AlertEmitter(channel="stdout").emit(
      "风险告警",
      details={"strategy": "demo"},
  )
  ```
- `TradingAlertService` 封装了常用交易事件（如风控阻断、流水线阶段失败）的告警调用。
- `PipelineController` 与 `run_managed_trading_cycle` 在检测到失败或风控拒绝时会自动调用告警，不需要额外配置。
- 风控策略模块 `RiskPolicy` 支持最大回撤、权益波动率、单标仓位、行业集中度以及持仓天数等阈值，可通过 `.env` 中的 `RISK_MAX_*` 配置，自 2025-11-03 版本起全部生效。

## 健康检查

- 使用 `env PYTHONPATH=src python scripts/healthcheck.py` 可执行基础健康检查：
  - 校验 `${REPORT_OUTPUT_DIR}/status.json` 是否存在且所有阶段状态正常；
  - 验证策略提示词模板包含必要占位符；
  - 成功返回码 `0`，失败会打印原因并返回非零。
- 可在 Docker 中将该脚本作为 `HEALTHCHECK` 命令，或结合监控平台定时执行。

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MONITORING_ALERT_CHANNEL` | `log` | 告警发布渠道（`log`/`stdout`/`stderr`）。 |
| `REPORT_OUTPUT_DIR` | `reports` | 状态文件与报表输出目录，健康检查与仪表盘将读取该目录。 |

## 后续路线

- 接入真实告警终端（如钉钉、邮件、Slack）时，可扩展 `AlertEmitter`。
- 将健康检查扩展为 FastAPI 路由，为 Kubernetes/Compose 提供 HTTP 模式的探针。
