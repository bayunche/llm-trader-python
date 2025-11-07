"""Actor 服务实现。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from llm_trader.db.models.enums import ModelRole
from llm_trader.model_gateway import ModelGateway
from llm_trader.model_gateway.service import GatewayResponse
from .schema import ActorDecisionPayload, ObservationSnapshot

if TYPE_CHECKING:  # pragma: no cover
    from llm_trader.observation.service import ObservationPayload


DEFAULT_ACTOR_SYSTEM_PROMPT = (
    "你是一名A股自动交易员。仅输出一个JSON对象，不包含额外文字。"
    "字段：decision_id,timestamp,observations_ref,account_view,actions,global_intent,notes。"
    "动作必须来自 [\"place_order\",\"modify_order\",\"cancel_order\",\"no_op\"]。"
    "确保价格>0、数量为最小交易单位整数倍，置信度在[0,1]，必要字段缺失时选择 no_op 并说明原因。"
)


@dataclass
class ActorContext:
    """Actor 调用上下文。"""

    session_id: str
    strategy_id: str
    objective: str
    model: Optional[str] = None


class ActorService:
    """封装 Actor 推理流程：构建 Prompt -> 调用模型 -> Pydantic 校验。"""

    def __init__(
        self,
        gateway: ModelGateway,
        *,
        system_prompt: str = DEFAULT_ACTOR_SYSTEM_PROMPT,
    ) -> None:
        self._gateway = gateway
        self._system_prompt = system_prompt

    def generate_decision(
        self,
        observation: "ObservationPayload" | Dict[str, Any],
        *,
        context: ActorContext,
    ) -> ActorDecisionPayload:
        payload_dict = self._snapshot_dict(observation)
        messages = self._build_messages(payload_dict, context)
        request_body = {
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        response = self._gateway.chat_completions(
            request_body,
            decision_id=None,
            role=ModelRole.ACTOR,
            model=context.model,
        )
        content = self._extract_message_content(response)
        decision = ActorDecisionPayload.model_validate_json(content)
        return decision

    def _snapshot_dict(self, observation: "ObservationPayload" | Dict[str, Any]) -> Dict[str, Any]:
        to_dict = getattr(observation, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        return observation

    def _build_messages(self, snapshot: Dict[str, Any], context: ActorContext) -> list[Dict[str, str]]:
        observation_payload = ObservationSnapshot.model_validate(snapshot).model_dump(mode="json")
        envelope = {
            "session": context.session_id,
            "strategy": context.strategy_id,
            "objective": context.objective,
            "observation": observation_payload,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": json.dumps(envelope, ensure_ascii=False)},
        ]

    def _extract_message_content(self, response: GatewayResponse) -> str:
        try:
            choices = response.payload["choices"]
            message = choices[0]["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - 防御
            raise ValueError("模型返回格式异常，缺少 message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ValueError("模型返回内容为空")
        return content


__all__ = ["ActorService", "ActorContext"]
