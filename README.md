# A股自动交易代理项目

> **执行者：Codex** ｜ **更新时间：2025-10-30**

本项目实现基于东方财富公开数据的自动化策略生成、回测、实盘模拟、可视化与报告体系，并支持风控、调度、容器化部署等完整能力。

## 功能概览

- **数据采集**：`data/pipelines` 支持代码表、交易日历、日/分钟行情、实时行情等同步，并统一落地至 `data_store/`，当实时行情未指定标的时会自动读取证券主表构建全集候选池。
- **策略生成**：`strategy/llm_generator.py` 调用大模型输出规则与 `selected_symbols`，配合 `strategy/generator.py` 进行本地规则搜索；策略版本通过 `strategy/repository.py` 管理。
- **回测引擎**：`backtest` 模块实现撮合、账户管理、指标计算与结果持久化，覆盖 T+1、费用、停牌等 A 股业务规则。
- **自动交易**：`trading/orchestrator.py` 串联行情、策略、信号与下单，实现“候选池 → 大模型选股 → 策略执行”；`trading/manager.py`+`trading/policy.py` 提供风险控制与上线/回滚机制；`pipeline/auto.py` 实现策略生成→回测验收→风控执行的全链路自动化。
- **API 服务**：`api/routes` 暴露数据、策略、回测、交易及 LLM 日志查询接口，统一通过 `require_api_key` 鉴权与限流。
- **可视化仪表盘**：`dashboard/app.py` 基于 Streamlit 展示资金曲线、多策略对比、流水明细与 LLM 日志，并支持 CSV 导出与 LLM 辅助诊断。
- **报告导出**：`reports/builder.py` 将交易数据生成 JSON/CSV/Markdown 报告，配套 `scripts/generate_report.py` 快速归档交易结果。
- **调度与监控**：`scheduler/manager.py` + `scripts/run_scheduler.py` 加载 JSON 配置启动 APScheduler 作业；`monitoring/alerts.py` 提供告警输出，`queue/simple.py` 作为事件总线原型。
- **容器化与自动化**：提供开发/生产 Dockerfile、Compose 配置以及 `scripts/run-prod-smoke.sh` 等辅助脚本，支持在容器内运行测试、执行自动化任务。
- **测试与验证**：`conda run -n llm-trader env PYTHONPATH=src python -m pytest` 覆盖 54 项单元/集成测试；`verification.md` 记录最新验证结果。

## 环境要求

- Python 3.10+
- Poetry >= 1.6（推荐）

## 快速开始

```bash
# 安装依赖
poetry install

# 进入虚拟环境
poetry shell

# 运行测试（即将补充具体用例）
poetry run pytest
```

### 使用 Conda（Python 3.10）环境

```bash
conda create -n llm-trader python=3.10
conda run -n llm-trader python -m pip install -r requirements.dev.txt
conda run -n llm-trader env PYTHONPATH=src python -m pytest
```

> 若网络无法直接访问 PyPI，可切换至国内镜像（例如 `https://pypi.tuna.tsinghua.edu.cn/simple`）。

## Docker 开发/测试

```bash
# 构建开发镜像并运行测试
bash scripts/run-tests-in-docker.sh

# 进入容器交互调试
docker compose -f docker-compose.dev.yml run --rm llm-trader-dev bash
```

> 容器会自动安装 `requirements.dev.txt` 中列出的全部依赖并挂载当前工作目录，确保在与本地一致的环境中运行 `pytest`。

## 仪表盘展示

```bash
conda run -n llm-trader streamlit run dashboard/app.py
```

- 默认读取本地 `data_store` 中的交易数据与 LLM 日志，可在侧边栏输入策略 ID 与会话 ID 进行切换。
- 页面包含资金曲线、订单/成交流水以及大模型提示记录，便于快速核对 AI 生成的策略与执行结果。

## 风控与上线

```bash
python scripts/run_managed_trading_cycle.py \
  --session session-demo \
  --strategy strategy-demo \
  --symbols 600000.SH 000001.SZ \
  --objective "获取稳健收益" \
  --max-drawdown 0.08 \
  --max-position-ratio 0.25
```

- `run_managed_trading_cycle.py` 会在执行交易循环后根据配置阈值评估最大回撤与单标的仓位占比，若超限则返回非零退出码并记录告警。
- 风险阈值亦可通过环境变量 `RISK_MAX_EQUITY_DRAWDOWN`、`RISK_MAX_POSITION_RATIO` 统一配置。
- 交易循环所需的会话 ID、策略 ID、**候选标的**、频率、初始资金、候选指标与调度间隔等均可在 `.env` 中通过 `TRADING_*` 变量配置，详见 `.env.example`。
- 若不传 `--symbols`，脚本会默认使用 `.env` 中的候选池；当候选池为空时会自动回退到证券主表的全量标的。
- 若启用大模型自动选股，`TRADING_SYMBOLS` 仅作为候选池；留空时系统会自动使用证券主表中的全量标的，可通过 `TRADING_SYMBOL_UNIVERSE_LIMIT` 控制候选数量，最终下单标的由模型返回的 `selected_symbols` 决定。
- 使用自建或多模型聚合的 OpenAI 兼容接口时，可设置 `TRADING_LLM_BASE_URL` 指向目标地址，并提供对应的 `OPENAI_API_KEY`/`LLM_TRADER_API_KEY`。

## 全链路自动化

```bash
python -m llm_trader.pipeline.auto \
  --session session-demo \
  --strategy strategy-demo \
  --symbols 600000.SH \
  --backtest-start 2024-01-01 \
  --backtest-end 2024-03-01
```

- 可使用 `AutoTradingConfig`/`run_full_automation` 在代码中串联“大模型策略生成 → 回测验收 → 风控执行”完整流程。
- 默认回测验收标准可通过 `BacktestCriteria` 配置，并在未达标时终止交易。
- 是否执行回测、收益/回撤阈值等自动化参数也可通过 `TRADING_RUN_BACKTEST`、`TRADING_BACKTEST_MIN_RETURN`、`TRADING_BACKTEST_MAX_DRAWDOWN` 等环境变量集中管理。
- 当自动化希望接入自定义模型服务时，同样支持配置 `TRADING_LLM_BASE_URL` 与 `TRADING_LLM_MODEL`，且模型可根据候选池自动筛选 `selected_symbols`。
- CLI 示例中仍需显式指定 `--symbols`；在调度或自定义调用场景中，可将候选池留空并依赖证券主表自动扩展。

## 报告导出

```bash
python -m llm_trader.reports.builder \
  --strategy strategy-demo \
  --session session-demo
```

- `ReportBuilder` 会将资金曲线、订单、成交与 LLM 日志导出为 CSV/JSON/Markdown 文件，默认输出到 `reports/` 目录。
- 可结合全链路自动化结果生成每次交易的归档报告。
```bash
python scripts/generate_report.py --strategy strategy-demo --session session-demo
```

## 调度与监控

- 调度：使用 `scripts/run_scheduler.py` 加载 JSON 配置（详见 `docs/scheduler.md`）即可统一调度实时行情、受控交易或全链路自动化任务。
- 若运行实时行情调度未显式指定 `--symbols`，系统会自动读取证券主表中已同步的全部有效标的作为候选池。
- 监控：`llm_trader.monitoring.AlertEmitter` 提供统一告警接口，可输出到日志或标准输出，方便接入外部告警系统（详见 `docs/monitoring.md`）。

## 容器化与部署

- 开发镜像：`Dockerfile.dev` + `docker-compose.dev.yml` 已提供开发环境，可在容器内运行 `pytest`、调度脚本等任务。
- 生产建议：基于 `pip install -r requirements.dev.txt` 或构建独立镜像，并通过 `scripts/run_scheduler.py` 搭配 JSON 配置完成任务编排。
- 简单使用示例：

```bash
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml run --rm llm-trader-dev bash
```
- 冒烟测试：`scripts/run-prod-smoke.sh` 会构建生产镜像并在容器内运行 `pytest` 进行快速回归。

### 一键启动脚本

- Linux/macOS：`./start.sh [up|down|restart|logs|status|sync-symbols|help] [service]`
- Windows PowerShell：`./start.ps1 -Command <up|down|restart|logs|status|sync-symbols|help> [-Service <name>]`

默认执行 `up`，会构建/更新镜像并在后台启动调度器；`sync-symbols` 可手动刷新证券主表，方便完全自动化的行情与选股流程。

docker-compose 会同时启动：
- `scheduler`：运行 `config/scheduler.prod.json` 中定义的实时行情、受控交易等任务
- `dashboard`：暴露 Streamlit 仪表盘（默认端口 `DASHBOARD_PORT=8501`）

### 完全自驱交易流程（推荐）

1. **准备环境变量**：复制 `.env.example` 为 `.env`，填写至少以下字段：
   - `OPENAI_API_KEY`（或兼容接口的 `LLM_TRADER_API_KEY`/`TRADING_LLM_BASE_URL`）
   - 如需限制候选池规模，可调整 `TRADING_SYMBOL_UNIVERSE_LIMIT`（默认 200）。
2. **同步证券主表（可选）**：`./start.sh sync-symbols`（或 PowerShell 版本）会在容器内运行 `SymbolsPipeline.sync()`，确保实时行情与大模型选股使用最新标的池。
3. **启动全部服务**：`./start.sh up` 或 `./start.ps1 -Command up`。首次会自动构建镜像并启动调度器 + 仪表盘。
4. **查看运行状况**：
   - 实时日志：`./start.sh logs scheduler` / `./start.ps1 -Command logs -Service scheduler`
   - 仪表盘：浏览器访问 `http://localhost:${DASHBOARD_PORT:-8501}`，可实时查看资金曲线、订单/成交、LLM 日志等。
5. **停止服务**：`./start.sh down`（或 PowerShell 等效命令）。

在“全自动”模式下，调度器会按 `config/scheduler.prod.json` 设定的频率执行：
- 自动同步实时行情（未显式给出标的时使用完整证券主表）
- 调用大模型从候选池挑选标的、生成策略、回测验收、执行交易并落地沙箱流水
- 仪表盘实时读取 `data_store/` 中的最新结果

## 文档索引

- 数据与回测设计：`docs/data_store.md`、`docs/backtest_design.md`
- 实时行情与大模型策略：`docs/realtime_data.md`、`docs/strategy_llm.md`
- 风控与调度：`docs/risk_management.md`、`docs/scheduler.md`、`docs/monitoring.md`
- 队列与事件：`docs/queue.md`

## 目录结构

```
llm-trader-python/
├── pyproject.toml        # Poetry 配置与依赖
├── 开发计划.md           # 待办式开发路线
├── README.md             # 项目简介与使用指南
├── src/
│   └── llm_trader/
│       └── __init__.py
├── tests/                # 测试用例目录（待完善）
├── data_store/           # 数据持久化目录（待完善）
└── .codex/               # 过程文档与日志
```

## 开发规范

- 严格遵守《开发计划.md》中的任务顺序与交付要求
- 所有代码注释与文档使用中文，优先复用主流生态组件
- 通过 `.codex/operations-log.md` 与 `.codex/testing.md` 记录操作与验证过程
- 禁止新增安全性设计或自研组件，如发现需立即移除

## API 访问控制

- 通过环境变量 `LLM_TRADER_API_KEY` 配置访问令牌，启用后所有 `/api/**` 路由需携带 `X-API-Key` 请求头。
- 使用 `LLM_TRADER_RATE_LIMIT`（默认 60）配置每分钟允许的请求次数；超过上限将返回 `HTTP 429`。
- 健康检查 `/api/health` 保持匿名访问，便于部署时的探活需求。

## 后续步骤

1. 根据 `开发计划.md` 执行阶段性任务，并在完成后更新计划状态
2. 为数据、策略、回测等核心模块补充实现与测试
3. 构建 API 与仪表盘，完善报告导出与调度监控能力

欢迎持续关注仓库更新。
