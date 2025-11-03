# A股自动交易代理项目

> **执行者：Codex** ｜ **更新时间：2025-11-03**  
> 当前版本已实现“数据采集 → 策略生成 → 自动交易 → 报表 → 仪表盘”单轮自动化，并提供状态文件供 Dashboard 展示整体执行情况。

---

## 当前能力概览

- **数据获取与存储**：`src/llm_trader/data/pipelines` 提供东方财富证券主表、交易日历、K线与实时行情同步，统一落地 `ParquetRepository`（`src/llm_trader/data/repositories/parquet.py`）。
- **大模型策略生成**：`LLMStrategyGenerator`（`src/llm_trader/strategy/llm_generator.py`）基于 OpenAI Chat Completions 输出策略规则与 `selected_symbols`，并在 `LLMStrategyLogRepository` 中留痕。
- **模拟交易执行**：`run_ai_trading_cycle`（`src/llm_trader/trading/orchestrator.py`）将实时行情、LLM 策略与历史数据结合，通过 `TradingSession` 复用回测撮合引擎，实现下单与账户记录。
- **自动化流水线**：`run_full_automation`（`src/llm_trader/pipeline/auto.py`）串联策略生成、历史回测、风险评估，便于构建全自动模拟流程。
- **调度与可视化**：`scripts/run_scheduler.py` 结合 APScheduler 执行数据/交易作业，`dashboard/app.py` 基于 Streamlit 展示资金曲线、订单、成交及 LLM 日志，支持提示词模板在线管理。
- **执行模式切换**：通过 `.env` 中的 `TRADING_EXECUTION_MODE` 和券商配置自动选择沙盒或实盘适配器；默认提供 mock 券商实现便于模拟 live 流程。
- **报表生成**：`llm_trader.reports` 支持将交易结果导出为 CSV/Markdown/JSON，自动化流程与 Docker 启动时会自动生成。

---

## 已知限制与规划中的变更

- **!!! 实盘执行尚不可用**：`TRADING_EXECUTION_MODE` 默认 `sandbox`，`live` 模式仍为占位实现，会在预检阶段直接阻断执行并给出警示，切勿在生产环境启用。
- **Docker 一键流程已上线**：`docker compose up` 会自动执行数据同步→策略生成→交易执行→报表生成→Dashboard 启动，并将状态写入 `REPORT_OUTPUT_DIR/status.json`。
- **外部依赖**：大模型调用需具备 OpenAI 兼容接口与 API Key；行情数据依赖东方财富公开端点（请遵守频控与条款）。
- **数据初始化**：首次运行必须先完成证券主表、行情等基础数据同步，否则自动化流程会因缺少数据而终止。

---

## 快速开始

```bash
# 安装依赖（Poetry）
poetry install

# 激活虚拟环境
poetry shell

# 运行测试（当前覆盖模拟与数据模块）
poetry run pytest
```

若使用 Conda：

```bash
conda create -n llm-trader python=3.10
conda run -n llm-trader python -m pip install -r requirements.dev.txt
conda run -n llm-trader env PYTHONPATH=src python -m pytest
```

### 数据初始化示例

```bash
# 同步证券主表
python -m llm_trader.data.pipelines.symbols

# 同步日线行情（示例）
python scripts/run_realtime_scheduler.py --symbols 600000.SH 000001.SZ
```

确保 `.env` 中填入：

- `OPENAI_API_KEY` 或兼容接口凭证；
- `TRADING_EXECUTION_MODE=sandbox`（默认；`live` 当前仅会抛出“未接入券商”提示，禁止启用）；
- `REPORT_OUTPUT_DIR`（报表与状态导出目录，默认 `reports`，请与宿主机挂载保持一致）；
- 可选：`PIPELINE_STATUS_FILENAME`（默认 `status.json`），用于指定状态文件名称。
- 若需模拟 live 流程，可设置 `TRADING_EXECUTION_MODE=live`，并配置 `TRADING_BROKER_PROVIDER`（默认为 `mock`）、`TRADING_BROKER_ACCOUNT` 等参数；接入真实券商时请替换 provider 并补充 `TRADING_BROKER_BASE_URL`、`TRADING_BROKER_API_KEY`。
- `MONITORING_ALERT_CHANNEL`（默认 `log`），用于选择告警输出渠道（`log`/`stdout`/`stderr`）。

---

## 关键模块速览

| 模块 | 说明 | 主要文件 | 关联测试 |
| --- | --- | --- | --- |
| 数据采集 | 东方财富数据抓取、落地与质量校验 | `src/llm_trader/data/pipelines/`, `src/llm_trader/data/repositories/parquet.py` | `tests/data/` |
| 策略生成 | LLM 提示构建、返回解析、规则封装 | `src/llm_trader/strategy/llm_generator.py`, `src/llm_trader/strategy/engine.py` | `tests/strategy/` |
| 交易执行 | LLM 建议→订单→执行（沙盒/占位实盘）→仓位记录 | `src/llm_trader/trading/orchestrator.py`, `src/llm_trader/trading/session.py`, `src/llm_trader/trading/execution_adapters.py` | `tests/trading/` |
| 自动化流水线 | 策略生成→回测→风控→报表生成 | `src/llm_trader/pipeline/auto.py` | `tests/pipeline/test_auto.py`, `tests/reports/test_builder.py` |
| 报表体系 | 数据加载、指标构建、文件写出 | `src/llm_trader/reports/*`, `scripts/generate_report.py` | `tests/reports/test_builder.py` |
| 调度与监控 | APScheduler 配置、告警、排程脚本 | `src/llm_trader/scheduler/`, `scripts/run_scheduler.py` | `tests/scheduler/` |
| 可视化 | Streamlit 仪表盘、LLM 日志辅助诊断 | `dashboard/app.py`, `dashboard/data.py` | `tests/dashboard/` |

---

## 使用示例

### 运行一次 AI 交易循环（模拟）
```bash
python scripts/run_ai_trading_cycle.py \
  --session demo-session \
  --strategy demo-strategy \
  --symbols 600000.SH 000001.SZ \
  --objective "获取稳健收益"
```
- 通过 LLM 生成规则与最终标的；
- 调用本地撮合引擎执行；
- 结果写入 `data_store/` 并在仪表盘中可视化。

### 启动全自动流水线
```bash
python -m llm_trader.pipeline.auto \
  --session demo-session \
  --strategy demo-strategy \
  --symbols 600000.SH \
  --backtest-start 2024-01-01 \
  --backtest-end 2024-03-01
```
- 自动执行策略生成、历史回测、风控决策；
- 若回测指标未达标，流程在风控前终止。

### 启动仪表盘与一键流程
```bash
conda run -n llm-trader streamlit run dashboard/app.py
```
- 访问 `http://localhost:8501` 查看资金曲线、订单、成交和 LLM 策略日志；
- 支持多策略/多会话对比以及 LLM 辅助问答。

> 生产环境可直接运行 `docker compose up`（或 `./start.sh up`）。容器内的入口脚本会执行新的管线控制器，将阶段结果写入 `${REPORT_OUTPUT_DIR}/${PIPELINE_STATUS_FILENAME}`，即使流程失败也会继续启动 Dashboard 并在页面顶部展示状态。

### 健康检查

```
env PYTHONPATH=src python scripts/healthcheck.py
```
- 检查最新状态文件是否存在且所有阶段均成功；
- 校验策略提示词模板占位符完整；
- 返回 0 代表健康，否则打印原因并返回非零退出码。

---

## 路线图（重点缺口与改造）

| 优先级 | 事项 | 目标 |
| --- | --- | --- |
| P0 | 接入真实券商执行适配器 | 在 `live` 模式下完成真实下单、资金同步与异常回滚，替换当前占位实现。 |
| P1 | 扩充监控与风控策略 | 增强交易后风险告警、配置化阈值、执行日志审计。 |
| P1 | 丰富测试资产 | 引入多标的、多频率、异常行情用例，覆盖沙盒/实盘模式与报表。 |
| P2 | 仪表盘性能与交互优化 | 提升大数据量下的加载体验，整合更多对比分析工具。 |
| P2 | Docker 周期化管道 | 在单容器环境中增加定时调度或多轮执行能力。 |

路线图对应的开发任务会同步体现在《开发计划.md》中，欢迎按需调整优先级。

---

## 贡献与验证

- 所有改动需同步更新 `.codex/operations-log.md`、`verification.md`；
- 测试统一使用 `env PYTHONPATH=src python -m pytest`；
- 文档更新请注明日期与执行者身份。
- 建议定期运行 `env PYTHONPATH=src python3 -m pytest tests/data/regression/test_data_quality.py` 与 `env PYTHONPATH=src python3 -m pytest tests/trading/test_manager.py` 验证数据与告警改造。

如需进一步需求沟通或接入新功能，请先更新《项目需求.md》与《开发计划.md》，保持文档与实现一致。
