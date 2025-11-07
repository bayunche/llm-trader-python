# 调度配置说明

> 更新时间：2025-11-05 ｜ 执行者：Codex

- 统一入口 `python app.py` 会在缺失配置时自动生成 `config/scheduler.prod.json`（基于环境变量），默认按照 `TRADING_SCHEDULER_INTERVAL`（默认 60 分钟）运行自动交易循环，可继续通过 `scripts/run_scheduler.py` 单独启动。
- 典型配置示例（与最新 `config/scheduler.prod.json` 一致）：

```json
{
  "timezone": "Asia/Shanghai",
  "jobs": [
    {
      "id": "realtime-quotes",
      "callable_path": "llm_trader.tasks.realtime.fetch_realtime_quotes",
      "trigger": "interval",
      "interval_minutes": 60,
      "kwargs": {}
    },
    {
      "id": "account-snapshot",
      "callable_path": "llm_trader.tasks.managed_cycle.sync_account_snapshot",
      "trigger": "interval",
      "interval_minutes": 60,
      "kwargs": {"symbol_universe_limit": 200}
    },
    {
      "id": "managed-trading",
      "callable_path": "llm_trader.tasks.managed_cycle.run_cycle",
      "trigger": "interval",
      "interval_minutes": 60,
      "kwargs": {
        "config": {
          "session_id": "session-demo",
          "strategy_id": "strategy-demo",
          "symbols": [],
          "objective": "自动交易",
          "indicators": ["sma", "ema"],
          "freq": "D",
          "initial_cash": 1000000.0,
          "llm_model": "gpt-4.1-mini",
          "only_latest_bar": true,
          "symbol_universe_limit": 200,
          "execution_mode": "sandbox",
          "selection_metric": "amount",
          "lookback_days": 120
        }
      }
    }
  ]
}
```

- `realtime-quotes` 任务在未提供 `symbols` 时会自动拉取最新标的池；`account-snapshot` 负责刷新账户资金与持仓，供观测构建和仪表盘使用。
- 可执行 `env PYTHONPATH=src python scripts/run_managed_scheduler.py --export-config config/scheduler.prod.json` 手动导出最新配置；亦可设置 `LLM_TRADER_SCHEDULER_CONFIG=/path/to/custom.json` 后运行 `python app.py` 或执行：

```bash
python scripts/run_scheduler.py custom_scheduler.json
```

- 代码内也可通过 `start_scheduler_from_dict` 动态构建调度器，与上述 JSON 结构保持一致。
- 调度任务 `llm_trader.tasks.managed_cycle.run_cycle` 会在每次执行后调用 `record_trading_run_summary` 写入 `trading_runs`，因此即便无真实成交也能在仪表盘“自动交易调用日志”标签快速查看 Prompt/Response 与风控结果。
