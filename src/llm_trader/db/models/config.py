from __future__ import annotations

"""
配置中心相关实体。
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from .enums import ModelRole, TradingMode


class ModelEndpoint(SQLModel, table=True):
    """模型端点配置。"""

    __tablename__ = "model_endpoints"

    model_alias: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="模型别名",
    )
    provider: str = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description="提供方",
    )
    endpoint_url: str = Field(
        sa_column=Column(String(256), nullable=False),
        description="兼容 OpenAI 的地址",
    )
    auth_type: str = Field(
        sa_column=Column(String(16), nullable=False),
        description="鉴权方式",
    )
    auth_secret_ref: str = Field(
        sa_column=Column(String(128), nullable=False),
        description="密钥引用",
    )
    default_params: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="默认参数",
    )
    retry_policy: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="重试策略",
    )
    routing: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="权重路由设置",
    )
    circuit_breaker: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="熔断规则",
    )
    cost_estimate: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="成本估算",
    )
    enabled: bool = Field(
        sa_column=Column(Boolean, nullable=False, default=True),
        description="是否启用",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="创建时间",
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="更新时间",
    )


class PromptTemplate(SQLModel, table=True):
    """提示词模板。"""

    __tablename__ = "prompt_templates"

    template_id: str = Field(
        sa_column=Column(String(64), primary_key=True),
        description="模板 ID",
    )
    role: ModelRole = Field(
        sa_column=Column(String(16), nullable=False, index=True),
        description="用途角色",
    )
    version: str = Field(
        sa_column=Column(String(32), nullable=False),
        description="版本号",
    )
    locale: str = Field(
        sa_column=Column(String(16), nullable=False),
        description="语言区域",
    )
    variables: list = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        description="变量列表",
    )
    guardrails: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="输出约束",
    )
    publish_status: str = Field(
        sa_column=Column(String(16), nullable=False),
        description="发布状态",
    )
    rollout_strategy: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="灰度策略",
    )
    change_log: str = Field(
        sa_column=Column(String(512), nullable=False),
        description="变更说明",
    )
    created_by: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="创建人",
    )
    updated_by: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="更新人",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="创建时间",
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="更新时间",
    )


class RiskConfiguration(SQLModel, table=True):
    """风控参数。"""

    __tablename__ = "risk_configurations"

    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
        description="自增主键",
    )
    limits: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="限额配置",
    )
    lists: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="白名单黑名单",
    )
    market_rules: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="市场规则",
    )
    posture: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="姿态策略",
    )
    version: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="版本号",
    )
    active: bool = Field(
        sa_column=Column(Boolean, nullable=False, default=True),
        description="是否激活",
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="创建时间",
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="更新时间",
    )
    updated_by: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="更新人",
    )


class SystemState(SQLModel, table=True):
    """系统统一启动状态记录。"""

    __tablename__ = "system_state"

    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
        description="自增主键",
    )
    current_mode: TradingMode = Field(
        sa_column=Column(String(32), nullable=False),
        description="当前执行模式",
    )
    components: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        description="各组件状态",
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="更新时间",
    )
    updated_by: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="更新操作者",
    )
