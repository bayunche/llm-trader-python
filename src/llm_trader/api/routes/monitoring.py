"""监控与审计相关 API。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import select

from llm_trader.api.schemas import LLMCallAuditItem, LLMCallAuditResponse
from llm_trader.api.security import require_api_key
from llm_trader.db.models import LLMCallAudit
from llm_trader.db.models.enums import ModelRole
from llm_trader.db.session import session_scope

router = APIRouter(prefix="/monitor", tags=["monitor"], dependencies=[Depends(require_api_key)])


@router.get("/llm-calls", response_model=LLMCallAuditResponse)
async def list_llm_calls(
    *,
    limit: int = Query(50, ge=1, le=500, description="返回的最大记录数"),
    decision_id: Optional[str] = Query(None, description="按决策 ID 过滤"),
    role: Optional[ModelRole] = Query(None, description="角色筛选（Actor/Checker 等）"),
    provider: Optional[str] = Query(None, description="模型提供方名称"),
    since: Optional[datetime] = Query(None, description="仅返回此时间之后的记录（UTC）"),
) -> LLMCallAuditResponse:
    """查询模型调用审计日志，支持按角色/决策/提供方过滤。"""

    statement = select(LLMCallAudit)
    if decision_id:
        statement = statement.where(LLMCallAudit.decision_id == decision_id)
    if role:
        statement = statement.where(LLMCallAudit.role == role)
    if provider:
        statement = statement.where(LLMCallAudit.provider == provider)
    if since:
        statement = statement.where(LLMCallAudit.created_at >= since)
    statement = statement.order_by(LLMCallAudit.created_at.desc()).limit(limit)
    with session_scope() as session:
        records: List[LLMCallAudit] = session.exec(statement).all()
    payload = [
        LLMCallAuditItem(
            trace_id=record.trace_id,
            decision_id=record.decision_id,
            role=record.role,
            provider=record.provider,
            model=record.model,
            tokens_prompt=record.tokens_prompt,
            tokens_completion=record.tokens_completion,
            latency_ms=record.latency_ms,
            cost=record.cost,
            created_at=record.created_at,
        )
        for record in records
    ]
    return LLMCallAuditResponse(code="OK", message="success", data=payload)


__all__ = ["router"]
