# LLM Trader · A 股大模型自动交易框架

> **执行者：Codex** ｜ **最后更新：2025-11-05**  
> 面向数据驱动的量化团队，提供“行情采集 → 策略生成 → 风险控制 → 执行复盘 → 仪表盘”一站式流水线。

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](#-快速开始) 
[![LLM](https://img.shields.io/badge/LLM-OpenAI%20API-blueviolet?logo=openai)](#-大模型策略设定) 
[![Tests](https://img.shields.io/badge/Tests-pytest-green?logo=pytest)](#-质量保证) 
[![Status](https://img.shields.io/badge/Status-Internal-orange)](#-社区与支持)

---

## 📌 快速索引

- [项目亮点](#-项目亮点)
- [架构总览](#-架构总览)
- [快速开始](#-快速开始)
- [使用指南](#-使用指南)
- [自动化交易全流程](#-自动化交易全流程)
- [配置项速查](#-配置项速查)
- [质量保证](#-质量保证)
- [路线图](#-路线图)
- [参与贡献](#-参与贡献)
- [社区与支持](#-社区与支持)
- [许可证](#-许可证)

---

## ✨ 项目亮点

- **全链路闭环**：内置 `scripts/run_full_pipeline.py`，实现行情同步、LLM 策略生成、风险评估、交易执行、报表输出的自动化。
- **大模型驱动策略**：`LLMStrategyGenerator` 使用 OpenAI Chat Completions 生成规则与标的，支持多场景提示词模板及日志追溯。
- **真实行情接入**：`OhlcvPipeline`、`RealtimeQuotesPipeline` 默认对接东方财富公开接口，并在证券主表采集阶段自动尝试多个 push2 子域；若外部接口不可用，会依次降级至上交所/深交所官方公开数据，再回退到本地 `metadata/symbols.parquet` 缓存，保障流程不中断。所有数据统一落地 `ParquetRepository`。
- **自动选股**：无需手动维护候选列表，系统会在全 A 股范围内按成交额/换手率等指标排序，选取前 `symbol_universe_limit` 个标的传递给大模型评估，可通过 `TRADING_SELECTION_METRIC` 自定义指标。
- **风险可控执行**：`run_managed_trading_cycle` 复用回测撮合引擎，结合 `RiskPolicy` 的回撤、波动、行业集中度等阈值做风控决策。
- **多格式报表与可视化**：`ReportBuilder` + `ReportWriter` 输出 CSV、Markdown、JSON，Streamlit 仪表盘支持实时交易看板、成交分布/趋势图、资金曲线对比及 LLM 日志浏览。
- **执行历史留痕**：每次自动交易循环会写入 `trading/runs/*.parquet`，记录大模型 prompt/response、策略规则、风控结论、订单与成交统计，可通过 API 或仪表盘回溯。
- **DevOps 友好**：Poetry/Conda 互通，Docker Compose 一键带起数据同步、策略执行、Dashboard。

---

## 🧱 架构总览

| 层级 | 职责 | 关键位置 |
| --- | --- | --- |
| 数据采集 | 东方财富证券主表、行情、实时快照同步与清洗 | `src/llm_trader/data/pipelines/`, `src/llm_trader/data/repositories/parquet.py` |
| 策略生成 | Prompt 模板管理 + LLM 规则解析 | `src/llm_trader/strategy/llm_generator.py`, `src/llm_trader/strategy/prompts.py` |
| 交易执行 | 实时行情摘要、订单生成、撮合记录 | `src/llm_trader/trading/orchestrator.py`, `src/llm_trader/trading/session.py` |
| 风控管理 | 账户权益监控、告警、行业风险约束 | `src/llm_trader/trading/manager.py`, `src/llm_trader/trading/policy.py` |
| 报表与可视化 | 报表管道 + Streamlit 仪表盘 | `src/llm_trader/reports/`, `dashboard/app.py` |
| 自动化管道 | 回测验证、受控执行与状态跟踪 | `src/llm_trader/pipeline/auto.py`, `scripts/run_full_pipeline.py` |

> 更多背景文档请访问 `docs/`：包括数据仓储 (`docs/data_store.md`)、风控 (`docs/risk_management.md`)、实时行情 (`docs/realtime_data.md`) 等。

---

## 🚀 快速开始

### 环境准备

```bash
# 使用 Poetry
poetry install
poetry shell

# 或使用 Conda
conda create -n llm-trader python=3.10
conda run -n llm-trader python -m pip install -r requirements.dev.txt
```

### 基础验证

```bash
env PYTHONPATH=src python -m pytest
```

### 必备配置

- 复制 `.env.example` → `.env`
- 填写 `OPENAI_API_KEY`（或兼容接口凭证）
- 确保 `DATA_STORE_DIR` 指向读写权限目录
- 推荐保持 `TRADING_EXECUTION_MODE=sandbox`

---

## 🛠 使用指南

### 1. 数据准备

```bash
# 同步证券主表
python -m llm_trader.data.pipelines.symbols

# 同步行情（示例）
python scripts/run_realtime_scheduler.py --symbols 600000.SH 000001.SZ
```

首轮运行请先完成证券主表与历史行情同步，否则自动化流程会直接阻断。  
同步成功后会在 `DATA_STORE_DIR/metadata/symbols.parquet` 缓存最近一次的证券主表，后续若东方财富及交易所接口全部失联，系统会自动使用该缓存继续运行。

### 2. 全流程自动化（本地运行）

1. 推荐方式：使用统一入口一次启动全流程、调度器与仪表盘（默认每 5 分钟自动调度）：  

   ```bash
   env PYTHONPATH=src python app.py
   ```

   - 首次启动会立即执行一次自动交易循环；
   - 后续由 APScheduler 根据 `config/scheduler.prod.json` 的设置每 5 分钟触发一次 `managed-trading` 任务；
   - Streamlit 仪表盘会自动在 `DASHBOARD_PORT`（默认 8501）监听，可通过 `LLM_TRADER_SCHEDULER_CONFIG` 指定其他调度配置，或设置 `LLM_TRADER_SKIP_INITIAL_PIPELINE=1` 跳过首次全量执行。
   - 调度任务 `run_cycle` 会与全流程脚本一致写入 `trading_runs` 摘要，包含大模型 Prompt/Response、风控结论等信息，供仪表盘新标签实时查看。

2. （可选）如仅需执行一次而不启动调度器，可继续使用原脚本：  

   - 确认 `.env` 中已配置以下核心项（可参考 `.env.example`）：  
   `TRADING_SESSION`, `TRADING_STRATEGY`, `TRADING_SYMBOLS`, `TRADING_OBJECTIVE`, `TRADING_FREQ`, `TRADING_LOOKBACK_DAYS`、`OPENAI_API_KEY` 等。  
   默认报表目录由 `TRADING_REPORT_OUTPUT_DIR` 控制（缺省为 `reports/`）。
   - 运行自动化脚本：

   ```bash
   env PYTHONPATH=src python scripts/run_full_pipeline.py
   ```

   该脚本会依次执行 **证券主表 & 实时/历史行情同步 → LLM 策略生成 → 回测验收 → 风控执行 → 报表写入**，并将阶段结果写入 `${REPORT_OUTPUT_DIR}/status.json`。证券主表步骤会先尝试东方财富多域名接口，若均失败则自动切换至上交所/深交所公开数据；如交易所接口仍不可用则会回退到本地缓存的 `symbols.parquet`。实时行情同步后会自动按 `TRADING_SELECTION_METRIC`（默认 `amount`）排序选出前 `TRADING_SYMBOL_UNIVERSE_LIMIT` 个标的传递给大模型。
   首次运行若网络受限仍建议预先拉取关键标的，脚本会在缺失时自动补齐指定窗口。

3. 产出的报表与 LLM 日志位于 `${REPORT_OUTPUT_DIR}/<strategy>/<session>/<timestamp>/`，可在仪表盘实时看板与图表模块中查看。
4. 若需自定义调度，可直接调用调度器脚本：

   ```bash
   env PYTHONPATH=src python scripts/run_scheduler.py config/scheduler.prod.json
   ```

   配置文件可自定义作业、频率与管道组合。

### 3. 单次 AI 交易循环（沙盒）

```bash
python scripts/run_ai_trading_cycle.py \
  --session demo-session \
  --strategy demo-strategy \
  --symbols 600000.SH 000001.SZ \
  --objective "获取稳健收益"
```

- 大模型生成策略规则与 `selected_symbols`  
- 复用本地撮合执行，结果写入 `data_store/`

### 4. 启动仪表盘

```bash
conda run -n llm-trader streamlit run dashboard/app.py
```

访问 `http://localhost:8501`，界面包含四个标签：**提示词管理**、**实时交易**、**自动交易历史** 与 **自动交易调用日志**。第四个标签聚合最新写入的 `trading_runs` 记录，可按策略/会话筛选并查看完整的 Prompt / Response，点击“刷新调用日志”按钮即可清除缓存并加载最新调度结果。

### 5. 查询历史摘要

- 全量流水线每次执行后会在 `data_store/trading/runs/strategy=<策略ID>/session=<会话ID>/runs.parquet` 写入历史摘要，包含大模型 Prompt/Response、策略规则、风控结论、订单与成交统计。
- 可通过 FastAPI 查询：

  ```bash
  curl -H "X-API-Key: ${LLM_TRADER_API_KEY}" \
       "http://127.0.0.1:8000/api/trading/history?strategy_id=strategy-llm&session_id=session-sandbox&limit=20"
  ```

  返回示例：

  ```json
  {
    "code": "OK",
    "message": "success",
    "data": [
      {
        "timestamp": "2025-11-04T03:35:56.585894",
        "status": "executed",
        "decision_proceed": true,
        "orders_executed": 1,
        "trades_filled": 1,
        "selected_symbols": ["600000.SH", "000001.SZ"],
        "suggestion_description": "基于短期均线与相对强弱指标的交易策略……",
        "rules": [...],
        "llm_prompt": "...",
        "llm_response": "{...}",
        "alerts": []
      }
    ]
  }
  ```

### 6. Docker 一键流程

```bash
docker compose -f docker-compose.prod.yml up --build
```

容器内入口脚本会执行完整流水线并启动 Dashboard。阶段状态持续写入 `${REPORT_OUTPUT_DIR}/status.json`。
同时，容器会调用 `python app.py`，先执行一次自动交易循环，再根据 `config/scheduler.prod.json` 自动每 5 分钟运行一次 `managed-trading` 任务；无需额外手动启动调度器。若需仅构建镜像，可执行 `docker compose build`。

---

## 🔄 自动化交易全流程

| 阶段 | 说明 | 关键实现 | 测试 |
| --- | --- | --- | --- |
| 行情采集 | 东方财富 K 线、实时行情采集与落地 | `src/llm_trader/data/pipelines/ohlcv.py`, `src/llm_trader/data/pipelines/realtime_quotes.py` | `tests/data/test_ohlcv_pipeline.py`, `tests/data/test_realtime_quotes.py` |
| 候选标的 | 周期同步证券主表，东方财富失败时降级至上/深交易所并最终回退本地缓存，生成候选列表 | `src/llm_trader/data/pipelines/symbols.py`, `_resolve_candidate_symbols` | `tests/data/test_symbols_pipeline.py`, `tests/trading/test_orchestrator.py` |
| 大模型策略 | Prompt 模板 → OpenAI → 规则解析与日志 | `src/llm_trader/strategy/llm_generator.py`, `src/llm_trader/strategy/prompts.py` | `tests/strategy/test_llm_generator.py`, `tests/strategy/test_prompts.py` |
| 交易执行 | 订单生成、撮合、账户快照 | `src/llm_trader/trading/orchestrator.py`, `src/llm_trader/trading/session.py` | `tests/trading/test_session.py`, `tests/trading/test_orchestrator.py` |
| 风险控制 | 回撤、仓位、行业集中度等阈值评估与告警 | `src/llm_trader/trading/manager.py`, `src/llm_trader/trading/policy.py` | `tests/trading/test_manager.py`, `tests/trading/test_policy.py` |
| 回测验收 | `BacktestRunner` 校验策略表现 | `src/llm_trader/pipeline/auto.py` | `tests/pipeline/test_auto.py`, `tests/pipeline/test_full_pipeline.py` |
| 报表输出 | 生成 CSV/Markdown/JSON + LLM 日志 | `src/llm_trader/reports/` | `tests/reports/test_builder.py` |
| 历史留痕 | 汇总模型输入输出、风控决策、订单统计 | `src/llm_trader/pipeline/auto.py`, `src/llm_trader/data/repositories/parquet.py`, `src/llm_trader/api/utils.py` | `tests/pipeline/test_auto.py`, `tests/data/test_trading_repository.py`, `tests/api/test_trading.py` |
| 状态追踪 | `PipelineController` 写入阶段状态与告警 | `scripts/run_full_pipeline.py` | 冒烟测试脚本 |

---

## ⚙️ 配置项速查

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 调用大模型所需凭证 | 无（必填） |
| `TRADING_EXECUTION_MODE` | `sandbox` / `live`，live 目前为 mock 实现 | `sandbox` |
| `TRADING_SYMBOLS` | 默认候选标的（留空则自动选股） | 空 |
| `TRADING_SYMBOL_UNIVERSE_LIMIT` | 自动选股时的最大候选数量 | `200` |
| `TRADING_SELECTION_METRIC` | 自动选股指标（`amount`/`volume`/`turnover_rate` 等） | `amount` |
| `TRADING_LOOKBACK_DAYS` | 自动化回测历史窗口天数 | `120` |
| `TRADING_REPORT_OUTPUT_DIR` | 报表及状态文件输出目录 | `reports` |
| `DATA_STORE_DIR` | Parquet 数据仓储根目录 | `data_store` |
| `MONITORING_ALERT_CHANNEL` | 告警输出渠道 `log`/`stdout`/`stderr` | `log` |

更多配置可在 `config/settings.py` 中查阅，支持 `.env` / 环境变量覆盖。

---

## ✅ 质量保证

- 推荐的测试流程：
  1. `env PYTHONPATH=src python3 -m pytest tests/decision tests/trading tests/tasks -q`（核心决策链路）
  2. `env PYTHONPATH=src python3 -m pytest tests/pipeline/test_auto.py -q`（自动化管线）
  3. `env PYTHONPATH=src python3 -m pytest tests/api/test_config_models.py -q`（配置中心）
  4. 在具备 PostgreSQL/Redis 的环境中执行 `env PYTHONPATH=src python3 -m pytest`，若仅有 SQLite 可使用 `PYTEST_ADDOPTS="--maxfail=1 --timeout=300"` 并预期 `tests/decision/test_decision_service.py` 因 JSONB 跳过。
  5. 数据回归：`env PYTHONPATH=src python3 -m pytest tests/data/test_trading_repository.py tests/data/regression/test_data_quality.py tests/data/test_symbols_pipeline.py -q`，验证 Parquet 仓储与多级降级策略。
- 运行前请确保本地或容器内提供 PostgreSQL（支持 JSONB）与 Redis；若使用 docker，可执行 `docker compose -f docker-compose.prod.yml up -d postgres redis`。
- 重点回归：`tests/data/regression/test_data_quality.py`、`tests/trading/test_manager.py`
- 文档与验证记录：`verification.md`、`.codex/testing.md`
- Health Check：`env PYTHONPATH=src python scripts/healthcheck.py`
- 离线/受限环境：
  - 使用 `env PYTHONPATH=.codex/vendor:src ...` 引入仓库随附的第三方依赖；如需额外包，请将对应 wheel/tarball 置于 `.codex/vendor/` 后执行 `python3 -m pip install --no-index --find-links .codex/vendor -r requirements.dev.txt`。
  - 当前缺少 `httpx==0.27.2` 的离线包，需提前下载或调整 requirements；否则请在具备外网的环境完成一次 `pip download` 并缓存。
  - 长耗时 pytest 可按模块分批执行，并为全量回归设置 `PYTEST_ADDOPTS="--maxfail=1 --timeout=600 --durations=10"` 观察慢用例，必要时在 `tests/data` 引入固定数据以避免外部请求。

### Docker 测试流程

> 适用于需要完整 PostgreSQL / Redis / Worker 的端到端验证场景。

1. **准备环境**
   - 安装 Docker 24+ 与 Compose 插件。
   - 将 `.env` 与 `config/` 下的必要配置复制到当前目录。
2. **构建镜像**
   ```bash
   docker compose -f docker-compose.prod.yml build
   ```
   或仅构建特定服务：
   ```bash
   docker compose -f docker-compose.prod.yml build api worker dashboard
   ```
3. **执行集成测试**
   ```bash
   docker compose -f docker-compose.prod.yml up --build --abort-on-container-exit
   ```
   - `api` 服务在启动脚本中会自动运行 `python -m pytest`，日志输出可在 `api` 容器终端查看。
   - `worker` / `dashboard` 会在 `postgres`、`redis` 就绪后拉起，便于观察实时数据。
4. **收集结果**
   - 测试日志：`docker compose logs api`.
   - 若需导出报告，可在 `reports/` 目录挂载宿主机路径。
5. **清理资源**
   ```bash
   docker compose -f docker-compose.prod.yml down -v
   ```
   释放容器与挂载卷。若测试失败，请在 `verification.md` 记录命令、日志摘要与失败原因。

> 注意：当前环境（LLM Trader 开发沙箱）禁用 Docker 命令，如需实际运行，请在拥有 Docker 权限的机器上执行并将日志粘贴回仓库。

---

## 🗺 路线图

| 优先级 | 事项 | 目标 |
| --- | --- | --- |
| P0 | 接入真实券商执行适配器 | 为 `live` 模式提供真实下单、资金同步与回滚能力 |
| P1 | 扩展风控指标生态 | 引入 VaR、敞口黑名单、日内波动限额等可配置指标 |
| P1 | 多账户/多策略提示词治理 | 独立模板仓库、审批流程与版本审计 |
| P2 | Docker 周期化管道 | 单容器内提供多轮执行与恢复策略 |
| P2 | 数据资产回溯 | 行情/报表归档与断档检测机制 |

路线图详情与优先级调整记录于《开发计划.md》。

---

## 🤝 参与贡献

1. Fork & 拉取子分支，保持小步提交，Commit message 使用祈使句。  
2. 修改前同步更新 `.codex/operations-log.md`、`verification.md`。  
3. 提交 PR 时请包含：变更摘要、测试命令/日志、关联任务。  
4. 文档更新需注明日期与执行者身份。  
5. 贡献者需遵循现有代码风格（PEP 8、中文注释、路径引用）。

> 若需新增模块，请先在《项目需求.md》与《开发计划.md》登记，确保文档与实现同步。

---

## 🧭 社区与支持

- 📚 文档：`docs/` 目录（数据存储、风控、调度、策略等）  
- 🧪 测试：`tests/` 下按模块划分的单元/集成测试  
- 🛠 工具：`scripts/` 提供数据同步、策略执行、报表生成脚本  
- ❓ 问题反馈：当前仅限内部 Issue / Scrum 频道

如需规划新特性，请在《项目需求.md》提交条目，或联系维护者。

---

## 📄 许可证

> **当前未公开对外许可证**，代码仅供内部评估与试运行，禁止传播或商用。  
后续若对外开源，将补充正式 License 文件并更新本说明。

---

感谢关注 LLM Trader！欢迎在 Dashboard 与报告中探索大模型驱动的量化交易新范式。 ✨
