# 调度配置说明

> 更新时间：2025-11-05 ｜ 执行者：Codex

- 统一入口 `python app.py` 会自动加载 `config/scheduler.prod.json`，默认每 5 分钟运行一次自动交易循环；仍可在其他场景下单独使用 `scripts/run_scheduler.py`。
- 典型配置示例（与 `config/scheduler.prod.json` 一致）：

```json
{
  "timezone": "Asia/Shanghai",
  "jobs": [
    {
      "id": "realtime-quotes",
      "callable_path": "llm_trader.tasks.realtime.fetch_realtime_quotes",
      "trigger": "interval",
      "interval_minutes": 5,
      "kwargs": {"symbols": ["600000.SH", "000001.SZ"]}
    },
    {
      "id": "managed-trading",
      "callable_path": "llm_trader.tasks.managed_cycle.run_cycle",
      "trigger": "interval",
      "interval_minutes": 5,
      "kwargs": {
        "config": {
          "session_id": "session-demo",
          "strategy_id": "strategy-demo",
          "symbols": ["600000.SH"],
          "objective": "自动调度",
          "history_start": "2024-01-01T00:00:00"
        }
      }
    }
  ]
}
```

- 如需自定义配置，可设置 `LLM_TRADER_SCHEDULER_CONFIG=/path/to/custom.json` 后运行 `python app.py`；或单独执行：

```bash
python scripts/run_scheduler.py custom_scheduler.json
```

- 代码内也可通过 `start_scheduler_from_dict` 动态构建调度器，与上述 JSON 结构保持一致。
