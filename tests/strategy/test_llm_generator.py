"""LLM 策略生成器测试。"""

from __future__ import annotations

import json
import pytest

from llm_trader.strategy.engine import RuleConfig
from llm_trader.strategy.llm_generator import (
    LLMStrategyContext,
    LLMStrategyGenerator,
)


def test_llm_generator_parses_rules() -> None:
    def fake_completion(prompt: str) -> str:
        payload = {
            "description": "均线突破策略",
            "rules": [
                {
                    "indicator": "sma",
                    "column": "close",
                    "params": {"window": 20},
                    "operator": ">",
                    "threshold": 10.5,
                }
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    generator = LLMStrategyGenerator(completion_fn=fake_completion)
    context = LLMStrategyContext(
        objective="提升日线收益",
        symbols=["600000.SH"],
        indicators=["sma", "ema"],
        historical_summary="近一月波动率 2%，上涨 5%",
    )
    suggestion = generator.generate(context)
    assert suggestion.description.startswith("均线突破")
    assert suggestion.rules[0] == RuleConfig(
        indicator="sma",
        column="close",
        params={"window": 20},
        operator=">",
        threshold=10.5,
    )
    assert generator.last_prompt is not None
    assert "提升日线收益" in generator.last_prompt
    assert generator.last_raw_response is not None


def test_llm_generator_raises_on_bad_json() -> None:
    generator = LLMStrategyGenerator(completion_fn=lambda _: "not json")
    context = LLMStrategyContext(
        objective="测试",
        symbols=["600000.SH"],
        indicators=["sma"],
        historical_summary="N/A",
    )
    with pytest.raises(ValueError):
        generator.generate(context)
