"""Checker 服务实现。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from llm_trader.db.models.enums import ModelRole
from llm_trader.model_gateway import ModelGateway
from llm_trader.model_gateway.service import GatewayResponse
from .schema import ActorDecisionPayload, CheckerResultPayload, ObservationSnapshot

if TYPE_CHECKING:  # pragma: no cover
    from llm_trader.observation.service import ObservationPayload


DEFAULT_CHECKER_SYSTEM_PROMPT = (
    "你是审单官，只负责检查 JSON 动作是否结构正确、取值合理、时间有效、动作无冲突。"
    "输入包含 observation 和 decision 两部分，输出固定格式："
    "{\"pass\": bool, \"reasons\": [...], \"observation_expired\": bool, \"conflicts\": [...], \"checked_at\": ISO8601}"
    "禁止添加额外文本，不要提出新的交易建议。"
)


@dataclass
class CheckerContext:
    """Checker 调用上下文。"""

    session_id: str
    strategy_id: str
    model: Optional[str] = None


class CheckerService:
    """封装 Checker 推理流程。"""

    def __init__(
        self,
        gateway: ModelGateway,
        *,
        system_prompt: str = DEFAULT_CHECKER_SYSTEM_PROMPT,
    ) -> None:
        self._gateway = gateway
        self._system_prompt = system_prompt

    def review(
        self,
        observation: "ObservationPayload" | Dict[str, Any],
        decision: ActorDecisionPayload | Dict[str, Any],
        *,
        context: CheckerContext,
    ) -> CheckerResultPayload:
        obs_dict = self._snapshot_dict(observation)
        if isinstance(decision, ActorDecisionPayload):
            decision_model = decision
        else:
            decision_model = ActorDecisionPayload.model_validate(decision)
        decision_dict = decision_model.model_dump(mode="json")
        messages = self._build_messages(obs_dict, decision_dict, context)
        request_body = {
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        response = self._gateway.chat_completions(
            request_body,
            decision_id=decision_dict.get("decision_id"),
            role=ModelRole.CHECKER,
            model=context.model,
        )
        content = self._extract_message_content(response)
        payload = CheckerResultPayload.model_validate_json(content)
        if payload.checked_at is None:
            payload.checked_at = datetime.now(tz=timezone.utc)
        return payload

    def _snapshot_dict(self, observation: "ObservationPayload" | Dict[str, Any]) -> Dict[str, Any]:
        to_dict = getattr(observation, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        return observation

    def _build_messages(
        self,
        observation: Dict[str, Any],
        decision: Dict[str, Any],
        context: CheckerContext,
    ) -> list[Dict[str, str]]:
        observation_payload = ObservationSnapshot.model_validate(observation).model_dump(mode="json")
        envelope = {
            "session": context.session_id,
            "strategy": context.strategy_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "observation": observation_payload,
            "decision": decision,
        }
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": json.dumps(envelope, ensure_ascii=False)},
        ]

    def _extract_message_content(self, response: GatewayResponse) -> str:
        try:
            choices = response.payload["choices"]
            content = choices[0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("模型返回格式异常，缺少 message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("模型返回内容为空")
        return content


__all__ = ["CheckerService", "CheckerContext"]
