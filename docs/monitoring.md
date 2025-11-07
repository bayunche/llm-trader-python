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

## 模型网关配置与指标

- 接口统一以 `X-API-Key` 进行鉴权，需在 `.env` 中设置 `LLM_TRADER_API_KEY`。
- **端点列表**：`GET /api/config/models`
  - 返回字段 `model_alias`、`provider`、`endpoint_url`、`weight`、`timeout`、`circuit_breaker`、`prompt_cost_per_1k` 等。
  - 用于查看当前生效的模型端点配置，响应格式为 `{"code": "OK", "data": [...]}`。
- **新增/更新端点**：`PUT /api/config/models`
  - 请求体字段与列表响应一致，支持热更新，调用成功后网关自动刷新缓存。
  - 可用于调整权重、熔断阈值、超时、成本估算等参数。
- **熔断指标**：`GET /api/config/models/metrics`
  - 返回每个端点的 `available`、`success_count`、`failure_count`、`consecutive_failures`、`opened_until`（UTC 时间）与 `last_error`。
  - 可结合 Prometheus 或内部监控周期获取，推荐在仪表盘中展示。
- 所有响应遵循 `ModelEndpointListResponse`/`ModelEndpointResponse`/`ModelEndpointMetricsResponse` 的包装格式，便于前端/脚本统一解析。

## 模型调用审计 API

- **接口**：`GET /api/monitor/llm-calls`
  - 支持查询参数：
    - `limit`（默认 50，最大 500）：返回的记录数量，按 `created_at` 倒序。
    - `decision_id`：仅返回指定决策关联的调用。
    - `role`：`actor`、`checker` 等，区分调用来源。
    - `provider`：模型提供方，如 `openai`、`azure`。
    - `since`：ISO8601 时间戳，仅返回此时间之后的记录。
  - 响应数据包含 `trace_id`、`decision_id`、`role`、`provider`、`model`、`tokens_prompt`、`tokens_completion`、`latency_ms`、`cost`、`created_at` 等字段，封装在 `LLMCallAuditResponse` 中。
- **用途**：仪表盘或 Prometheus 抓取 Agent 模型调用日志，分析 Actor/Checker 的延迟、成本、token 消耗，可结合 `decision_id` 追溯到决策总账。
- **鉴权**：同其它 API，一律通过 `X-API-Key`。

## 决策审计 API

- **接口**：`GET /api/trading/decisions`
  - 查询决策总账（DecisionLedger）与风控结论（RiskResult），默认返回最近 50 条，可通过 `limit`（≤200）、`status`（如 `executed`/`rejected_risk`）、`since`（UTC 时间）过滤。
  - 响应每条记录包含：`decision_id`、`status`、`observation_ref`、`actor_model`、`checker_model`、`risk_summary`、`created_at`、`executed_at`，以及嵌套的 `risk_result`（`passed`、`reasons`、`corrections`、`evaluated_at`）。
  - 可用于仪表盘展示最近的 Actor/Checker → Risk → Execution 闭环信息，或导出审计报表。
- **接口**：`GET /api/trading/decisions/{decision_id}`
  - 返回指定决策的完整细节：`DecisionAction` 列表、`CheckerResult`、`RiskResult`、`DecisionLedger` 摘要、备注等，可辅以后续扩展（例如关联 LLM trace）。
  - 结合 `/api/monitor/llm-calls` 可实现“从决策到模型调用”的追溯闭环。

## 决策审计与风险指标

- **数据库表**：
  - `decisions` / `decision_actions`：Actor 输出及动作明细。
  - `checker_results`：Checker 审单结论（pass/fail、原因、冲突）。
  - `risk_results`：Risk Gate 通过与告警列表。
  - `decision_ledger`：对外审计视图，记录 `observation_ref`、模型版本、风险摘要、执行结果与时间。
  - `llm_call_audit`：模型调用 trace（trace_id、provider、token 使用、延迟、成本）。
- **日志关联**：所有环节使用 `decision_id`、`trace_id` 串联，可在日志平台按 `decision_id=<value>` 追踪 Actor → Checker → Risk → Execution。
- **访问方式**：
  - SQL 查询示例：`SELECT status, actor_model, checker_model, risk_summary FROM decision_ledger ORDER BY created_at DESC LIMIT 20;`
  - 计划中的 REST/WS（后续迭代）：`GET /api/trading/decisions`、`GET /api/trading/decisions/{id}`、`WS /api/ws/decisions`，返回上述数据结构。
  - `reports/strategy=<id>/session=<id>/<timestamp>/manifest.json` 中记录 `decision_id`、风险结论、生成时间，可用于 Runbook 与合规审查。
- **Prometheus 指标建议**：
  - `decision_latency_ms{stage=actor|checker|risk|exec}`：各阶段耗时。
  - `decision_status_total{status}`：executed / rejected_checker / rejected_risk 的数量。
  - `risk_alert_total{reason}`：Risk Gate 告警分布（需从日志或 `risk_results` 表聚合导出）。
