from __future__ import annotations

"""
审计与决策总账实体。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from .enums import DecisionStatus, ModelRole


class DecisionLedger(SQLModel, table=True):
    """决策总账记录。"""

    __tablename__ = "decision_ledger"

    id: Optional[int] = Field(
        default=None,
        sa_column=Column("id", type_=int, primary_key=True, autoincrement=True),
        description="自增主键",
    )
    decision_id: str = Field(
        sa_column=Column(
            String(64),
            ForeignKey("decisions.decision_id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        description="关联决策 ID",
    )
    observation_ref: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="观测引用",
    )
    actor_model: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="Actor 模型",
    )
    checker_model: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="Checker 模型或规则集",
    )
    actor_json_ref: Optional[str] = Field(
        default=None,
        sa_column=Column(String(128), nullable=True),
        description="Actor 原始输出存储位置",
    )
    checker_json_ref: Optional[str] = Field(
        default=None,
        sa_column=Column(String(128), nullable=True),
        description="Checker 原始输出存储位置",
    )
    risk_summary: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="风控摘要",
    )
    status: DecisionStatus = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description="决策最终状态",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="记录创建时间",
    )
    executed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="首次执行时间",
    )

    decision = Relationship(back_populates="ledger")


class LLMCallAudit(SQLModel, table=True):
    """模型调用审计日志。"""

    __tablename__ = "llm_call_audit"

    trace_id: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="调用链标识",
    )
    decision_id: Optional[str] = Field(
        default=None,
        sa_column=Column(
            String(64),
            ForeignKey("decisions.decision_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        description="关联决策",
    )
    role: ModelRole = Field(
        sa_column=Column(String(16), nullable=False, index=True),
        description="调用角色",
    )
    provider: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="模型提供方",
    )
    model: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="模型名称",
    )
    prompt_hash: str = Field(
        sa_column=Column(String(128), nullable=False),
        description="提示词哈希",
    )
    tokens_prompt: int = Field(
        sa_column=Column("tokens_prompt", type_=int, nullable=False),
        description="提示 token 数",
    )
    tokens_completion: int = Field(
        sa_column=Column("tokens_completion", type_=int, nullable=False),
        description="输出 token 数",
    )
    latency_ms: int = Field(
        sa_column=Column("latency_ms", type_=int, nullable=False),
        description="延迟（毫秒）",
    )
    cost: float = Field(
        sa_column=Column("cost", type_=float, nullable=False, default=0.0),
        description="成本估计",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="记录时间",
    )
