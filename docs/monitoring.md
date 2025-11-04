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

# 仪表盘概览扩展

最新版本的 Streamlit 仪表盘除了原有的 Pipeline 状态、订单/成交流水、策略日志与提示词管理外，新增了以下能力：

- **实时交易看板**：展示最近成交与订单（含策略说明、刷新按钮、CSV 导出），便于快速回溯策略行为。
- **图表增强**：
  - 资金曲线对比支持多策略交互、导出；
  - 成交金额分布图（Top N 标的）；
  - 成交金额趋势图（按标的筛选）；
  - 成交流水原始数据可直接在页面查看并下载。

> 若需接入真实告警终端（如钉钉、邮件、Slack），可在 `AlertEmitter` 上扩展；健康检查脚本后续也可升级为 FastAPI 路由以支持 HTTP 探针。
