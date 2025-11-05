"""初始化 llm_trader PostgreSQL 架构。"""

from __future__ import annotations

from alembic import op

from llm_trader.db import metadata  # noqa: F401
from llm_trader.db.models import (  # noqa: F401
    AccountSnapshot,
    CheckerResult,
    Decision,
    DecisionAction,
    DecisionLedger,
    Fill,
    LLMCallAudit,
    MasterSymbol,
    ModelEndpoint,
    Observation,
    Order,
    PerformanceSnapshot,
    PromptTemplate,
    RiskConfiguration,
    RiskResult,
    SystemState,
)

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    创建全部核心表。
    """
    bind = op.get_bind()
    metadata.create_all(bind=bind)


def downgrade() -> None:
    """
    回滚时删除全部核心表。
    """
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
