"""Actor 与 Checker 服务使用的 Pydantic 数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ObservationSnapshot(BaseModel):
    """用于 Prompt 的观测数据快照."""

    model_config = ConfigDict(extra="allow")

    observation_id: str = Field(..., min_length=1)
    generated_at: datetime
    valid_ttl_ms: int = Field(..., gt=0)
    account: Dict[str, object]
    universe: List[str] = Field(default_factory=list)
    features: Dict[str, object] = Field(default_factory=dict)
    market_rules: Dict[str, object] = Field(default_factory=dict)


class DecisionActionPayload(BaseModel):
    """Actor 输出的单个动作。"""

    model_config = ConfigDict(extra="forbid")

    type: Literal["place_order", "modify_order", "cancel_order", "no_op"]
    symbol: Optional[str] = None
    side: Optional[Literal["buy", "sell"]] = None
    order_type: Optional[Literal["limit", "market"]] = None
    price: Optional[float] = Field(default=None, gt=0)
    qty: Optional[int] = Field(default=None, gt=0)
    tif: Optional[Literal["day", "ioc", "fok"]] = None
    target_order_id: Optional[str] = None
    intent_rationale: Optional[str] = Field(default=None, max_length=240)
    intent_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_action(self) -> "DecisionActionPayload":
        if self.type in {"place_order", "modify_order"}:
            missing = [
                name
                for name, value in {
                    "symbol": self.symbol,
                    "side": self.side,
                    "order_type": self.order_type,
                    "qty": self.qty,
                }.items()
                if value is None
            ]
            if missing:
                raise ValueError(f"动作 {self.type} 缺失字段: {', '.join(missing)}")
            if self.order_type == "limit" and self.price is None:
                raise ValueError("限价委托必须包含 price")
        if self.type in {"modify_order", "cancel_order"} and not self.target_order_id:
            raise ValueError("改单/撤单动作必须提供 target_order_id")
        return self


class ActorDecisionPayload(BaseModel):
    """Actor 返回的决策 JSON。"""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(..., min_length=1)
    timestamp: datetime
    observations_ref: str = Field(..., min_length=1)
    account_view: Dict[str, float]
    global_intent: Optional[Dict[str, object]] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    actions: List[DecisionActionPayload] = Field(default_factory=list)

    @field_validator("actions")
    @classmethod
    def ensure_actions(cls, actions: List[DecisionActionPayload]) -> List[DecisionActionPayload]:
        if not actions:
            raise ValueError("决策必须包含至少一个动作")
        return actions


class CheckerResultPayload(BaseModel):
    """Checker 输出的审单结果。"""

    model_config = ConfigDict(extra="forbid")

    passed: bool = Field(alias="pass")
    reasons: List[str] = Field(default_factory=list)
    observation_expired: bool = Field(default=False)
    conflicts: List[Dict[str, object]] = Field(default_factory=list)
    checked_at: Optional[datetime] = None

    @model_validator(mode="after")
    def normalize(self) -> "CheckerResultPayload":
        if self.passed and self.reasons:
            raise ValueError("通过的审单结果不应包含拒绝原因")
        return self


__all__ = [
    "ActorDecisionPayload",
    "DecisionActionPayload",
    "CheckerResultPayload",
    "ObservationSnapshot",
]
