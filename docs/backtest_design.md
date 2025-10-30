# 回测引擎设计草案

> 更新时间：2025-10-29 ｜ 执行者：Codex

## 1. 模块划分

- `src/llm_trader/backtest/models.py`：账户、持仓、订单、成交等领域模型
- `src/llm_trader/backtest/execution.py`：撮合逻辑（T+1、涨跌停、费用、停牌），通过 `ExecutionConfig` 参数化
- `src/llm_trader/backtest/engine.py`：回测主循环、信号处理、绩效统计
- `src/llm_trader/backtest/metrics.py`：指标计算（净值、最大回撤、夏普等）
- `ParquetRepository.write_backtest_result`：回测结果持久化（权益曲线、交易流水）
- `src/llm_trader/backtest/persist.py`：结果存储（复用 ParquetRepository）

## 2. 数据流程

1. 从数据层拉取 K 线与基础指标
2. 信号生成模块输出目标仓位/交易指令
3. 撮合引擎根据当日收盘信号、次日开盘成交规则执行
4. 更新账户状态、记录成交流水
5. 计算绩效指标并保存到 `backtests/` 目录

## 3. 关键规则

- **T+1**：买入当日不可卖出；配置 `allow_same_day_sell` 以兼容未来场景
- **涨跌停**：根据输入的上/下限价格判断是否成交
- **费用模型**：支持佣金、印花税、过户费，提供默认参数
- **整数手**：所有股票交易量为 100 的整数倍
- **停牌/退市**：禁止买入，持仓保持

## 4. 数据结构草案

### 账户

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| cash | float | 可用资金 |
| positions | Dict[symbol, Position] | 持仓字典 |
| equity_curve | List[DailyPerformance] | 净值序列 |

### 持仓

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| symbol | str | 证券代码 |
| volume | int | 持仓股数 |
| cost_price | float | 最新成本价 |
| frozen | bool | 是否被冻结（停牌） |

### 订单 & 成交

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| order_id | str | 订单标识 |
| symbol | str | 标的 |
| side | str | buy/sell |
| volume | int | 数量（股） |
| price | float | 下单价格（信号价） |
| status | str | created/filled/partial/cancelled |
| filled_volume | int | 成交数量 |
| filled_amount | float | 成交金额 |

## 5. 测试计划

- 单元测试：撮合规则、费用计算、T+1 限制
- 集成测试：简单策略（双均线）跑通全流程
- 回归测试：与已知示例比对最大回撤、夏普
