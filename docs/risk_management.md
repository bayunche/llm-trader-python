# 风险控制与上线流程

> 更新时间：2025-10-30 ｜ 执行者：Codex

## 1. 风险阈值配置

- 通过环境变量或 `.env` 文件配置以下阈值：
  - `RISK_MAX_EQUITY_DRAWDOWN`：允许的最大权益回撤（百分比，默认 `0.1` 表示 10%）。
  - `RISK_MAX_POSITION_RATIO`：单标的最大仓位占比（默认 `0.3`）。
- 应用启动时 `AppSettings.risk` 会读取并缓存该配置，可在代码中通过 `get_settings().risk` 访问。

## 2. 风险策略执行流程

1. `run_managed_trading_cycle.py` 使用 `TradingCycleConfig` 触发一次完整的行情→策略→下单流程。
2. 交易执行结束后，`RiskPolicy` 会读取最新的权益曲线与仓位快照，评估：
   - 当前最大回撤是否超出阈值；
   - 单标的仓位占比是否超出阈值。
3. 若存在风险，脚本返回非零退出码并输出详细告警消息，可由任务编排器捕获后触发报警或回滚流程。

## 3. 上线与回滚建议

- 在生产调度中建议先运行 `scripts/run_managed_trading_cycle.py` 或全链路脚本的 Dry Run 检验风险。
- 若触发风险告警，应暂停后续交易流程，并将对应会话标记为只读，查看 `data_store/strategies/llm_logs` 中的提示记录排查原因。
- 回滚流程可通过保留的策略版本（`StrategyRepository`）加载上一轮的策略参数，然后重新执行交易循环。

## 4. 告警集成

- 默认告警输出到日志（`trading.risk`），可结合日志收集或自定义回调接入企业 IM/邮件。
- 后续可扩展 `RiskPolicy` 的 `alert_callback` 与调度脚本，实现多渠道通知和自动化响应。
