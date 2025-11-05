from __future__ import annotations

"""
核心数据实体：观测、决策、动作、审单与风控。
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from .enums import (
    ActionType,
    CheckerResultStatus,
    ClockPhase,
    DecisionStatus,
    OrderSide,
    OrderStatus,
    OrderTimeInForce,
    OrderType,
    RiskPosture,
)

if TYPE_CHECKING:
    from .audit import DecisionLedger


class Observation(SQLModel, table=True):
    """交易观测快照。"""

    __tablename__ = "observations"

    observation_id: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="观测唯一标识",
    )
    generated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="观测生成时间",
    )
    valid_ttl_ms: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="观测有效时长（毫秒）",
    )
    clock_phase: ClockPhase = Field(
        sa_column=Column(String(32), nullable=False),
        description="交易时钟阶段",
    )
    account_nav: float = Field(
        sa_column=Column(Float, nullable=False),
        description="账户权益",
    )
    account_cash: float = Field(
        sa_column=Column(Float, nullable=False),
        description="可用资金",
    )
    account_risk_posture: RiskPosture = Field(
        sa_column=Column(String(32), nullable=False),
        description="当前风险姿态",
    )
    positions: List[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="持仓列表",
    )
    universe: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="本轮可操作标的集合",
    )
    features: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="标的特征及行情数据",
    )
    market_rules: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="市场规则（tick、lot、涨跌停）",
    )
    risk_snapshot: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="风险评估相关指标",
    )

    decisions: List["Decision"] = Relationship(back_populates="observation")


class Decision(SQLModel, table=True):
    """Actor 决策实体。"""

    __tablename__ = "decisions"

    decision_id: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="决策唯一标识",
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="决策时间戳",
    )
    observation_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("observations.observation_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="引用的观测 ID",
    )
    account_nav: float = Field(
        sa_column=Column(Float, nullable=False),
        description="决策时账户权益视图",
    )
    account_cash: float = Field(
        sa_column=Column(Float, nullable=False),
        description="决策时账户可用资金视图",
    )
    global_intent_risk_posture: Optional[RiskPosture] = Field(
        default=None,
        sa_column=Column(String(32), nullable=True),
        description="全局风险姿态建议",
    )
    global_intent_max_new_margin: Optional[float] = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
        description="本轮新增资金占用上限",
    )
    notes: Optional[str] = Field(
        default=None,
        sa_column=Column(String(500), nullable=True),
        description="策略说明",
    )

    observation: Observation = Relationship(back_populates="decisions")
    actions: List["DecisionAction"] = Relationship(back_populates="decision")
    checker_result: Optional["CheckerResult"] = Relationship(back_populates="decision")
    risk_result: Optional["RiskResult"] = Relationship(back_populates="decision")
    orders: List["Order"] = Relationship(back_populates="decision")
    ledger: Optional["DecisionLedger"] = Relationship(back_populates="decision")


class DecisionAction(SQLModel, table=True):
    """决策动作明细。"""

    __tablename__ = "decision_actions"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
        description="自增主键",
    )
    decision_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("decisions.decision_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="所属决策",
    )
    type: ActionType = Field(
        sa_column=Column(String(32), nullable=False),
        description="动作类型",
    )
    symbol: Optional[str] = Field(
        default=None,
        sa_column=Column(String(32), nullable=True),
        description="涉及标的",
    )
    side: Optional[OrderSide] = Field(
        default=None,
        sa_column=Column(String(8), nullable=True),
        description="下单方向",
    )
    order_type: Optional[OrderType] = Field(
        default=None,
        sa_column=Column(String(16), nullable=True),
        description="委托类型",
    )
    price: Optional[float] = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
        description="委托价格",
    )
    qty: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
        description="委托数量（股）",
    )
    tif: Optional[OrderTimeInForce] = Field(
        default=None,
        sa_column=Column(String(8), nullable=True),
        description="时效设定",
    )
    target_order_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
        description="改单/撤单目标订单",
    )
    intent_rationale: Optional[str] = Field(
        default=None,
        sa_column=Column(String(240), nullable=True),
        description="动作意图说明",
    )
    intent_confidence: Optional[float] = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
        description="置信度 [0,1]",
    )

    decision: Decision = Relationship(back_populates="actions")


class CheckerResult(SQLModel, table=True):
    """审单结果。"""

    __tablename__ = "checker_results"

    decision_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("decisions.decision_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        description="关联决策",
    )
    status: CheckerResultStatus = Field(
        sa_column=Column(String(8), nullable=False),
        description="审单结论",
    )
    reasons: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="拒绝原因",
    )
    checked_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="审单时间",
    )
    observation_expired: bool = Field(
        sa_column=Column(Boolean, nullable=False, default=False),
        description="观测是否过期",
    )
    conflicts: List[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="动作冲突列表",
    )

    decision: Decision = Relationship(back_populates="checker_result")


class RiskResult(SQLModel, table=True):
    """硬风控结果。"""

    __tablename__ = "risk_results"

    decision_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("decisions.decision_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        description="关联决策",
    )
    passed: bool = Field(
        sa_column=Column(Boolean, nullable=False),
        description="是否通过风控",
    )
    reasons: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="拒绝原因列表",
    )
    corrections: List[dict] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="可行修正建议",
    )
    evaluated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="风控评估时间",
    )

    decision: Decision = Relationship(back_populates="risk_result")


class Order(SQLModel, table=True):
    """委托记录。"""

    __tablename__ = "orders"

    order_id: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="订单唯一标识",
    )
    client_order_id: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True),
        description="幂等键",
    )
    decision_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("decisions.decision_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        description="来源决策",
    )
    symbol: str = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description="标的代码",
    )
    side: OrderSide = Field(
        sa_column=Column(String(8), nullable=False),
        description="买卖方向",
    )
    order_type: OrderType = Field(
        sa_column=Column(String(16), nullable=False),
        description="委托类型",
    )
    price: Optional[float] = Field(
        default=None,
        sa_column=Column(Float, nullable=True),
        description="委托价格",
    )
    qty: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="数量",
    )
    tif: OrderTimeInForce = Field(
        sa_column=Column(String(8), nullable=False),
        description="时效策略",
    )
    status: OrderStatus = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description="订单状态",
    )
    broker: str = Field(
        sa_column=Column(String(32), nullable=False),
        description="执行通道",
    )
    placed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="委托时间",
    )
    risk_passed: bool = Field(
        sa_column=Column(Boolean, nullable=False),
        description="风控是否通过",
    )
    risk_detail: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="风控摘要",
    )

    decision: Optional[Decision] = Relationship(back_populates="orders")
    fills: List["Fill"] = Relationship(back_populates="order")


class Fill(SQLModel, table=True):
    """成交记录。"""

    __tablename__ = "fills"

    fill_id: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="成交唯一标识",
    )
    order_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("orders.order_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="关联订单",
    )
    symbol: str = Field(
        sa_column=Column(String(32), nullable=False),
        description="成交标的",
    )
    qty: float = Field(
        sa_column=Column(Float, nullable=False),
        description="成交数量",
    )
    price: float = Field(
        sa_column=Column(Float, nullable=False),
        description="成交价格",
    )
    fee: float = Field(
        sa_column=Column(Float, nullable=False, default=0.0),
        description="费用",
    )
    filled_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="成交时间",
    )

    order: Order = Relationship(back_populates="fills")
