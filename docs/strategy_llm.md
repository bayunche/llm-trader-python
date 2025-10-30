# 大模型策略生成说明

> 更新时间：2025-10-29 ｜ 执行者：Codex

## 1. 模块概览

- `src/llm_trader/strategy/llm_generator.py`：封装 `LLMStrategyGenerator`，通过 OpenAI Chat Completion 输出策略规则。
- 主要入口：
  - `LLMStrategyContext`：描述目标、标的、候选指标、历史摘要等上下文。
  - `LLMStrategyGenerator.generate(context)`：返回 `LLMStrategySuggestion`（含描述与 `RuleConfig` 列表）。
- 可通过注入 `completion_fn` 在测试或离线环境中使用假数据。

## 2. 输出约定

大模型返回 JSON 格式，包含：

```json
{
  "description": "策略说明",
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

- `operator` 仅支持 `>`, `>=`, `<`, `<=`, `cross_up`, `cross_down`。
- `params` 为键值对，将直接传入 `RuleConfig.params`。

## 3. 使用示例

```python
from llm_trader.strategy.llm_generator import LLMStrategyGenerator, LLMStrategyContext

context = LLMStrategyContext(
    objective="提升日线收益并控制回撤",
    symbols=["600000.SH", "000001.SZ"],
    indicators=["sma", "ema", "momentum"],
    historical_summary="近一月波动率 2%，收益 5%，回撤 1.5%"
)

generator = LLMStrategyGenerator(model="gpt-4o-mini")
suggestion = generator.generate(context)

print(suggestion.description)
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

## 5. 注意事项

- 生成结果需通过回测验证，避免直接用于实盘决策。
- 建议在 Prompt 中明确约束（指标集合、阈值范围、风控要求），提高可用性。
- 若大模型返回格式不符合要求，`LLMStrategyGenerator` 会抛出 `ValueError` 以便调用方处理。
- 后续可扩展为多轮交互：先生成规则，再根据回测反馈请求调整。 
