"""基于大模型的策略生成器。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from llm_trader.strategy.engine import RuleConfig

try:  # pragma: no cover - 在测试中会通过依赖注入替代
    from openai import OpenAI
except Exception:  # pragma: no cover - 无 openai 依赖时
    OpenAI = None  # type: ignore


@dataclass
class LLMStrategyContext:
    """向大模型提供的上下文信息。"""

    objective: str
    symbols: Sequence[str]
    indicators: Sequence[str]
    historical_summary: str


@dataclass
class LLMStrategySuggestion:
    """大模型返回的策略建议。"""

    description: str
    rules: List[RuleConfig]


class LLMStrategyGenerator:
    """调用大模型生成策略规则。"""

    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        completion_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        self.model = model
        self._completion_fn = completion_fn
        self._client = None
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None
        if completion_fn is None:
            if OpenAI is None:
                raise RuntimeError("openai 库未安装，无法使用 LLMStrategyGenerator")
            resolved_key = api_key or os.getenv("OPENAI_API_KEY")
            if not resolved_key:
                raise RuntimeError("缺少 OPENAI_API_KEY，无法调用大模型")
            self._client = OpenAI(api_key=resolved_key)

    def generate(self, context: LLMStrategyContext) -> LLMStrategySuggestion:
        prompt = self._build_prompt(context)
        self.last_prompt = prompt
        raw = self._invoke_model(prompt)
        self.last_raw_response = raw
        return self._parse_response(raw)

    def _build_prompt(self, context: LLMStrategyContext) -> str:
        symbols_text = ", ".join(context.symbols)
        indicators_text = ", ".join(context.indicators)
        prompt = f"""
你是一名量化分析师，需要根据输入的背景和历史表现生成可执行的股票策略规则。
请输出 JSON，包含字段：
* description: 策略概述（中文）
* rules: 数组，每项含 indicator, column, params(对象), operator, threshold

约束：
1. 指标必须来自候选集合：{indicators_text}
2. 阈值为数值，operator 仅允许 ">", ">=", "<", "<=", "cross_up", "cross_down"
3. params 需是 JSON 对象，如 {{"window": 20}}
4. 至少返回 1 条规则

目标：{context.objective}
标的：{symbols_text}
历史表现摘要：{context.historical_summary}
"""
        return prompt.strip()

    def _invoke_model(self, prompt: str) -> str:
        if self._completion_fn is not None:
            return self._completion_fn(prompt)
        assert self._client is not None  # for mypy
        response = self._client.chat.completions.create(  # type: ignore[attr-defined]
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一名量化策略生成助手，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        message = response.choices[0].message
        content = getattr(message, "content", None)
        if not content:
            raise ValueError("大模型未返回内容")
        return content

    def _parse_response(self, raw: str) -> LLMStrategySuggestion:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("无法解析大模型返回的 JSON") from exc

        description = data.get("description", "")
        rules_payload = data.get("rules", [])
        if not isinstance(rules_payload, list) or not rules_payload:
            raise ValueError("大模型未返回有效的规则列表")

        rules: List[RuleConfig] = []
        for idx, rule_data in enumerate(rules_payload):
            try:
                rules.append(
                    RuleConfig(
                        indicator=rule_data["indicator"],
                        column=rule_data.get("column", "close"),
                        params=rule_data.get("params", {}),
                        operator=rule_data["operator"],
                        threshold=float(rule_data["threshold"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"第 {idx + 1} 条规则解析失败：{exc}") from exc

        return LLMStrategySuggestion(description=description, rules=rules)


__all__ = ["LLMStrategyGenerator", "LLMStrategyContext", "LLMStrategySuggestion"]
