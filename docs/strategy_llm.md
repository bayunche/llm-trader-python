# 大模型策略生成说明

> 更新时间：2025-10-29 ｜ 执行者：Codex

## 1. 模块概览

- `src/llm_trader/strategy/llm_generator.py`：封装 `LLMStrategyGenerator`，通过 OpenAI 兼容接口输出策略规则与标的建议。
- 主要入口：
  - `LLMStrategyContext`：描述目标、标的、候选指标、历史摘要等上下文。
  - `LLMStrategyGenerator.generate(context)`：返回 `LLMStrategySuggestion`（含描述、`selected_symbols` 与 `RuleConfig` 列表）。
- 可通过注入 `completion_fn` 在测试或离线环境中使用假数据。

## 2. 输出约定

大模型返回 JSON 格式，包含：

```json
{
  "description": "策略说明",
  "selected_symbols": ["600000.SH", "000001.SZ"],
  "rules": [
    {
      "indicator": "sma",
      "column": "close",
      "params": {"window": 20},
      "operator": ">",
      "threshold": 10.5
    }
  ]
}
```

- `selected_symbols` 必须是候选标的的子集，后续流程将以此进行撮合及回测。
- `operator` 仅支持 `>`, `>=`, `<`, `<=`, `cross_up`, `cross_down`。
- `params` 为键值对，将直接传入 `RuleConfig.params`。

## 3. 使用示例

```python
from llm_trader.strategy.llm_generator import LLMStrategyGenerator, LLMStrategyContext

context = LLMStrategyContext(
    objective="提升日线收益并控制回撤",
    symbols=["600000.SH", "000001.SZ", "600519.SH"],  # 候选标的
    indicators=["sma", "ema", "momentum"],
    historical_summary="近一月波动率 2%，收益 5%，回撤 1.5%"
)

generator = LLMStrategyGenerator(model="gpt-4o-mini", base_url="https://multi-llm.example/v1")
suggestion = generator.generate(context)

print(suggestion.description)
print("选定标的:", suggestion.selected_symbols)
for rule in suggestion.rules:
    print(rule)
```

> 需要预先设置 `OPENAI_API_KEY` 或在初始化时传入 `api_key`。

## 4. 与策略评估集成

生成的规则可直接传入 `StrategyGenerator` 或 `BacktestRunner`：

```python
from llm_trader.strategy.generator import StrategyGenerator, RuleSpace
from llm_trader.strategy import StrategyCandidate

# 将 LLM 生成的规则包装成 StrategyCandidate
candidate = StrategyCandidate(rules=suggestion.rules, metrics={}, equity_curve=[])

# 交由评估流程进行回测和指标验证
```

在 `tests/strategy/test_llm_generator.py` 中提供了示例测试，使用 `completion_fn` 注入 JSON 响应，可在无 OpenAI 环境下运行。

## 5. 提示词模板管理

自版本 2025-11-03 起，提示词通过模板管理器统一加载：

- 默认模板位于 `config/prompts/strategy.txt`，包含 `{objective}`、`{symbols}`、`{indicators}`、`{historical_summary}` 占位符。
- 用户自定义模板存储在 `data_store/prompts/templates/<name>.txt`，`PromptTemplateManager` 会自动优先读取该文件。
- Streamlit 仪表盘提供提示词管理面板，可查看、编辑、保存或重置模板；保存后下一次交易循环立即生效。
- 模板缺少必要占位符时将抛出 `ValueError("提示词模板缺少占位符")`，请确保模板内容保持必需字段。

## 6. 注意事项

- 模块会校验 `selected_symbols` 非空，若未提供或不规范将抛出 `ValueError`。
- 可在环境变量中设置 `TRADING_LLM_BASE_URL`、`OPENAI_API_KEY` 以接入多模型聚合服务，同时通过 `TRADING_SYMBOL_UNIVERSE_LIMIT` 控制候选池规模。
- 生成结果需经过回测与风控验证，避免直接用于实盘决策。
- 建议在提示词中明确约束（候选标的、指标、风险目标），提高可用性。
- 若大模型返回格式不符合要求，`LLMStrategyGenerator` 会抛出 `ValueError` 以便调用方处理。
- 后续可扩展为多轮交互：先生成规则，再根据回测反馈请求调整。 

## 7. 执行模式与风险提示

- 自动化管线会读取 `TRADING_EXECUTION_MODE` 并在预检阶段记录到状态文件；`sandbox` 为默认安全模式。
- `live` 模式默认使用 Mock 券商客户端模拟真实流程；若配置 `TRADING_BROKER_PROVIDER` 为真实券商，则需确保 API Key、Base URL、账户等参数完整。
- 尚未接入真实券商时，请勿在生产环境启用 live 模式；接入真实券商后务必补充风险控制与额度校验。
