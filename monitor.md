# Phase C 监控与告警扩展计划

> 更新时间：2025-11-03 ｜ 执行者：Codex

## 目标

- 提供实时与离线告警能力：涵盖回撤、仓位占比、自动化任务失败等场景。
- 统一监控配置入口，支持本地与 Docker 部署。
- 补充健康检查端点，便于容器与外部监控平台使用。

## 交付项

1. **告警渠道抽象**：在 `llm_trader.monitoring` 增加告警发布接口，默认实现日志/邮件/钉钉（mock）。
2. **告警触发点**：
   - `PipelineController` 阶段失败时触发告警。
   - `run_managed_trading_cycle` 风控拒绝时推送回撤/仓位信息。
   - 数据同步任务失败时触发通知。
3. **健康检查**：新增 `scripts/healthcheck.py` 或 FastAPI 路由，检查数据存储、历史数据、策略模板以及最近一次流水线状态文件。
4. **配置管理**：在 `.env` 中开放告警渠道及阈值配置（如 `MONITORING_ALERT_CHANNEL`, `ALERT_WEBHOOK_URL`）。
5. **测试与文档**：
   - pytest 覆盖告警触发逻辑（使用 fake publisher）。
   - README/开发计划/项目需求同步说明 Phase C 能力。

## 时间规划

| 步骤 | 内容 | 预估 | 备注 |
| --- | --- | --- | --- |
| C1.1 | 告警抽象与默认实现 | 1.5 天 | 新增 `monitoring/alerts.py` 扩展接口 |
| C1.2 | 自动化流程告警接入 | 1 天 | PipelineController、run_managed_trading_cycle |
| C1.3 | 健康检查脚本/接口 | 1 天 | Docker healthcheck & CLI |
| C1.4 | 文档与测试补充 | 0.5 天 | 更新 README、verification.md、tests |

## 验收标准

- 当任一阶段失败或风控拒绝时，告警接口被调用并可在日志中确认。
- Docker 启动后运行 `python scripts/healthcheck.py` 返回 0 表示健康。
- 所有告警配置可通过 `.env` 覆盖；禁用告警时不会抛出异常。
- README 与 docs 中提供告警配置使用说明；verification.md 记录健康检查命令。
