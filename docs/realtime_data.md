# 实时行情采集说明

> 更新时间：2025-10-29 ｜ 执行者：Codex

## 1. 模块概览

- `src/llm_trader/data/pipelines/realtime_quotes.py`：东方财富实时行情抓取，周期性拉取最新报价并落盘。
- `src/llm_trader/data/repositories/parquet.py`：新增 `write_realtime_quotes`，按日期/证券分区写入 `data_store/realtime/quotes/`。
- `src/llm_trader/tasks/realtime.py`：封装 APScheduler 调度，可按分钟级触发抓取任务。
- `scripts/run_realtime_scheduler.py`：命令行脚本，用于启动实时行情调度。

## 2. 数据落盘结构

```
data_store/
└── realtime/
    └── quotes/
        └── date=YYYY-MM-DD/
            └── quotes_{symbol}_{YYYYMMDD}.parquet
```

单个文件包含该日期内某只股票的多次快照，字段包括：
`symbol`, `name`, `last_price`, `change`, `change_ratio`, `volume`, `amount`, `high`, `low`, `open`, `prev_close`, `turnover_rate`, `amplitude`, `pe`, `snapshot_time` 等。

## 3. 调度使用

```bash
# 指定候选标的，按 1 分钟间隔抓取
python scripts/run_realtime_scheduler.py --symbols 600000.SH 000001.SZ --interval 1

# 若省略 --symbols，将自动读取证券主表（symbols.parquet）中的全部有效标的
python scripts/run_realtime_scheduler.py --interval 1
```

脚本基于 APScheduler 的 `BackgroundScheduler`，支持 Ctrl+C 优雅退出。

## 4. 注意事项

- 单次请求最多 50 个证券，管道内部已自动切分；如需更大规模抓取，可多进程/多任务配置。
- 未显式指定标的时，实时行情管道会根据证券主表自动构建标的池，需确保已执行 `SymbolsPipeline.sync()`。
- 接口存在速率限制，建议结合阶段 8 的监控与限流配置使用。
- 落盘文件按日期追加，可配合 BI/Streamlit 仪表盘进行实时展示。
- 若需与大模型策略生成联动，可结合 `StrategyRepository` 自动登记最新信号。
