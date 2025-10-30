# 数据存储设计说明

> 更新时间：2025-10-29 ｜ 执行者：Codex

## 1. 目录结构

```
data_store/
├── metadata/                # 证券主表、交易日历等静态元数据
├── ohlcv/
│   ├── daily/               # 日线数据
│   └── intraday/            # 分钟线数据
├── fundamentals/            # 基础指标与财务摘要
├── strategies/
│   └── signals/             # 策略信号（策略ID + 版本分区）
└── backtests/               # 回测结果（策略ID + 运行日期）
```

- 所有目录均在运行时自动创建，避免手工初始化。
- Parquet 文件按数据集类型分层，支持按频率/证券/日期分区。

## 2. 数据集定义

| 数据集 | 目录 | 分区模板 | 文件名模板 | 说明 |
| --- | --- | --- | --- | --- |
| Symbols | `metadata/` | - | `symbols.parquet` | 证券主表元数据 |
| TradingCalendar | `metadata/` | - | `trading_calendar.parquet` | A股交易日历 |
| OHLCV(日线) | `ohlcv/daily/` | `freq={freq}/symbol={symbol}/year={year}/month={month}` | `{date}.parquet` | 日线行情 |
| OHLCV(分钟) | `ohlcv/intraday/` | `freq={freq}/symbol={symbol}/date={date}` | `{symbol}_{freq}.parquet` | 分钟线行情 |
| Fundamentals | `fundamentals/` | `symbol={symbol}/year={year}` | `{symbol}_{year}.parquet` | 基础指标 |
| StrategySignals | `strategies/signals/` | `strategy={symbol}/version={freq}` | `signals.parquet` | 策略信号输出 |
| BacktestResults | `backtests/` | `strategy={symbol}/run_date={date}` | `result.parquet` | 回测结果 |

> 说明：StrategySignals/BacktestResults 中的 `symbol` 字段复用为策略ID，`freq` 字段用于表示策略版本或频率。

## 3. Schema 概览

核心实体字段定义位于 `src/llm_trader/data/schemas/definitions.py`，通过 `EntitySchema` / `FieldSpec` 描述字段类型、主键与说明：

- `SYMBOLS_SCHEMA`：证券主表
- `TRADING_CALENDAR_SCHEMA`：交易日历
- `OHLCV_SCHEMA`：K线行情
- `FUNDAMENTALS_SCHEMA`：基础指标

这些 Schema 将用于数据采集、校验与文档同步，确保字段含义一致。

## 4. 代码支持

- `src/llm_trader/data/storage.py`：提供 `DataStoreManager`、`DatasetConfig`、`DatasetKind` 等工具，用于统一生成文件路径。
- `default_manager()`：内置所有默认数据集配置，可直接调用 `path_for()` 获取具体文件路径。

示例：

```python
from datetime import datetime
from llm_trader.data import default_manager, DatasetKind

manager = default_manager()
path = manager.path_for(
    DatasetKind.OHLCV_DAILY,
    symbol="600000.SH",
    freq="D",
    timestamp=datetime(2024, 7, 1),
)
print(path)
# data_store/ohlcv/daily/freq=D/symbol=600000.SH/year=2024/month=07/20240701.parquet
```

## 5. 后续扩展

- 增加更多基础指标或衍生指标时，仅需补充 `DatasetKind` 与 `DatasetConfig`。
- 若需要分布式存储（如 S3），可替换 `data_store_dir` 实现，保持接口不变。
- 数据质量校验模块将基于 Schema 对落盘数据进行验证，保证字段一致性。
