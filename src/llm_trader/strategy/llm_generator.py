"""基于大模型的策略生成器。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from llm_trader.strategy.engine import RuleConfig
from llm_trader.strategy.prompts import PromptTemplateManager

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
    selected_symbols: List[str]


class LLMStrategyGenerator:
    """调用大模型生成策略规则。"""

    def __init__(
        self,
        *,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        completion_fn: Optional[Callable[[str], str]] = None,
        template_manager: Optional[PromptTemplateManager] = None,
        template_name: str = "strategy",
    ) -> None:
        self.model = model
        self._base_url = base_url
        self._completion_fn = completion_fn
        self._client = None
        self._template_manager = template_manager or PromptTemplateManager()
        self._template_name = template_name
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None
        if completion_fn is None:
            if OpenAI is None:
                raise RuntimeError("openai 库未安装，无法使用 LLMStrategyGenerator")
            resolved_key = api_key or os.getenv("OPENAI_API_KEY")
            if not resolved_key:
                raise RuntimeError("缺少 OPENAI_API_KEY，无法调用大模型")
            client_kwargs = {"api_key": resolved_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            self._client = OpenAI(**client_kwargs)  # type: ignore[arg-type]

    def generate(self, context: LLMStrategyContext) -> LLMStrategySuggestion:
        prompt = self._build_prompt(context)
        self.last_prompt = prompt
        raw = self._invoke_model(prompt)
        self.last_raw_response = raw
        return self._parse_response(raw)

    def _build_prompt(self, context: LLMStrategyContext) -> str:
        symbols_text = ", ".join(context.symbols)
        indicators_text = ", ".join(context.indicators)
        template = self._template_manager.load_template(self._template_name)
        try:
            prompt = template.content.format(
                objective=context.objective,
                symbols=symbols_text,
                indicators=indicators_text,
                historical_summary=context.historical_summary,
            )
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(f"提示词模板缺少占位符：{missing}") from exc
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

        selected_symbols = data.get("selected_symbols") or data.get("symbols")
        if not isinstance(selected_symbols, list) or not selected_symbols:
            raise ValueError("大模型未指定交易标的 selected_symbols")
        normalized_symbols = [str(symbol).strip() for symbol in selected_symbols if str(symbol).strip()]
        if not normalized_symbols:
            raise ValueError("selected_symbols 为空")

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

        return LLMStrategySuggestion(description=description, rules=rules, selected_symbols=normalized_symbols)


__all__ = ["LLMStrategyGenerator", "LLMStrategyContext", "LLMStrategySuggestion"]
