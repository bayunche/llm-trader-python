# 调度配置说明

> 更新时间：2025-10-30 ｜ 执行者：Codex

- 使用 `scripts/run_scheduler.py` + JSON 配置即可在 APScheduler 上注册多个任务。
- 示例配置：

```json
{
  "timezone": "Asia/Shanghai",
  "jobs": [
    {
      "id": "realtime",
      "callable_path": "llm_trader.tasks.realtime.fetch_realtime_quotes",
      "trigger": "interval",
      "interval_minutes": 5,
      "kwargs": {"symbols": ["600000.SH", "000001.SZ"]}
    },
    {
      "id": "managed-cycle",
      "callable_path": "llm_trader.tasks.managed_cycle.run_cycle",
      "trigger": "interval",
      "interval_minutes": 60,
      "kwargs": {
        "config": {
          "session_id": "session-demo",
          "strategy_id": "strategy-demo",
          "symbols": ["600000.SH"],
          "objective": "自动测试",
          "history_start": "2024-01-01T00:00:00"
        }
      }
    }
  ]
}
```

- 初次使用可运行：

```bash
python scripts/run_scheduler.py scheduler_config.json
```

- 在 CI/生产中亦可通过 `start_scheduler_from_dict` 直接在代码中加载。
