"""交易数据查询 API。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from llm_trader.api.responses import success_response
from llm_trader.api.schemas import (
    CheckerResultItem,
    DecisionActionItem,
    DecisionDetailItem,
    DecisionDetailResponse,
    DecisionLedgerItem,
    DecisionLedgerResponse,
    RiskResultItem,
    TradingEquityResponse,
    TradingLogResponse,
    TradingOrderResponse,
    TradingRunHistoryResponse,
    TradingTradeResponse,
)
from llm_trader.api.utils import (
    load_llm_logs,
    load_trading_equity,
    load_trading_orders,
    load_trading_runs,
    load_trading_trades,
)
from llm_trader.api.security import require_api_key
from llm_trader.db.models import (
    Decision,
    DecisionAction,
    DecisionLedger,
    RiskResult,
    CheckerResult,
    LLMCallAudit,
)
from llm_trader.db.session import session_scope
from llm_trader.db.models.enums import DecisionStatus


router = APIRouter(prefix="/trading", tags=["trading"], dependencies=[Depends(require_api_key)])


@router.get("/orders", response_model=TradingOrderResponse, summary="查询交易订单流水")
async def list_trading_orders(
    strategy_id: str = Query(..., description="策略 ID"),
    session_id: str = Query(..., description="会话 ID"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="返回条数上限"),
) -> TradingOrderResponse:
    records = load_trading_orders(strategy_id=strategy_id, session_id=session_id, limit=limit)
    return success_response(records)


@router.get("/trades", response_model=TradingTradeResponse, summary="查询交易成交流水")
async def list_trading_trades(
    strategy_id: str = Query(...),
    session_id: str = Query(...),
    limit: Optional[int] = Query(None, ge=1, le=1000),
) -> TradingTradeResponse:
    records = load_trading_trades(strategy_id=strategy_id, session_id=session_id, limit=limit)
    return success_response(records)


@router.get("/equity", response_model=TradingEquityResponse, summary="查询资金曲线与持仓快照")
async def list_trading_equity(
    strategy_id: str = Query(...),
    session_id: str = Query(...),
    limit: Optional[int] = Query(None, ge=1, le=1000),
) -> TradingEquityResponse:
    records = load_trading_equity(strategy_id=strategy_id, session_id=session_id, limit=limit)
    return success_response(records)


@router.get("/logs", response_model=TradingLogResponse, summary="查询 LLM 策略日志")
async def list_trading_logs(
    strategy_id: str = Query(...),
    session_id: str = Query(...),
    limit: Optional[int] = Query(None, ge=1, le=1000),
) -> TradingLogResponse:
    records = load_llm_logs(strategy_id=strategy_id, session_id=session_id, limit=limit)
    return success_response(records)


@router.get("/history", response_model=TradingRunHistoryResponse, summary="查询交易历史摘要")
async def list_trading_history(
    strategy_id: str = Query(..., description="策略 ID"),
    session_id: str = Query(..., description="会话 ID"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="返回条数上限"),
    offset: int = Query(0, ge=0, description="从最早记录起跳过的条数"),
) -> TradingRunHistoryResponse:
    records = load_trading_runs(
        strategy_id=strategy_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )
    return success_response(records)


@router.get("/decisions", response_model=DecisionLedgerResponse, summary="查询决策审计记录")
async def list_decisions(
    limit: int = Query(50, ge=1, le=200, description="返回的最大记录数"),
    status: Optional[str] = Query(None, description="DecisionStatus 过滤"),
    since: Optional[datetime] = Query(None, description="仅返回此时间之后的记录（UTC）"),
) -> DecisionLedgerResponse:
    with session_scope() as session:
        ledger_records = _load_decision_records(session, limit=limit, status=status, since=since)
        decision_ids = [record.decision_id for record in ledger_records]
        risk_map = _load_risk_map(session, decision_ids)
    payload = [
        DecisionLedgerItem(
            decision_id=record.decision_id,
            status=record.status,
            observation_ref=record.observation_ref,
            actor_model=record.actor_model,
            checker_model=record.checker_model,
            risk_summary=record.risk_summary or {},
            created_at=record.created_at,
            executed_at=record.executed_at,
            risk_result=risk_map.get(record.decision_id),
        )
        for record in ledger_records
    ]
    return DecisionLedgerResponse(code="OK", message="success", data=payload)


@router.get("/decisions/{decision_id}", response_model=DecisionDetailResponse, summary="查询单个决策详情")
async def get_decision(decision_id: str) -> DecisionDetailResponse:
    with session_scope() as session:
        detail = _load_decision_detail(session, decision_id)
    if detail is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "决策不存在"})
    return DecisionDetailResponse(code="OK", message="success", data=detail)


def _load_decision_records(session, *, limit: int, status: Optional[str], since: Optional[datetime]):
    statement = select(DecisionLedger)
    if status:
        statement = statement.where(DecisionLedger.status == status)
    if since:
        statement = statement.where(DecisionLedger.created_at >= since)
    statement = statement.order_by(DecisionLedger.created_at.desc()).limit(limit)
    return session.exec(statement).all()


def _load_risk_map(session, decision_ids):
    risk_map = {}
    if not decision_ids:
        return risk_map
    risk_records = session.exec(
        select(RiskResult).where(RiskResult.decision_id.in_(decision_ids))
    ).all()
    for item in risk_records:
        risk_map[item.decision_id] = RiskResultItem(
            decision_id=item.decision_id,
            passed=item.passed,
            reasons=item.reasons or [],
            corrections=item.corrections or [],
            evaluated_at=item.evaluated_at,
        )
    return risk_map


def _load_decision_detail(session, decision_id: str) -> Optional[DecisionDetailItem]:
    decision = session.get(Decision, decision_id)
    if decision is None:
        return None
    actions_records = session.exec(
        select(DecisionAction).where(DecisionAction.decision_id == decision_id)
    ).all()
    actions = [
        DecisionActionItem(
            type=str(action.type),
            symbol=action.symbol,
            side=str(action.side) if action.side else None,
            order_type=str(action.order_type) if action.order_type else None,
            price=action.price,
            qty=action.qty,
            tif=str(action.tif) if action.tif else None,
            target_order_id=action.target_order_id,
        )
        for action in actions_records
    ]
    checker = session.get(CheckerResult, decision_id)
    checker_item = None
    if checker is not None:
        checker_item = CheckerResultItem(
            status=checker.status.value,
            reasons=list(checker.reasons or []),
            observation_expired=checker.observation_expired,
            checked_at=checker.checked_at,
        )
    ledger = session.exec(
        select(DecisionLedger).where(DecisionLedger.decision_id == decision_id)
    ).first()
    ledger_item = (
        DecisionLedgerItem(
            decision_id=ledger.decision_id,
            status=ledger.status,
            observation_ref=ledger.observation_ref,
            actor_model=ledger.actor_model,
            checker_model=ledger.checker_model,
            risk_summary=ledger.risk_summary or {},
            created_at=ledger.created_at,
            executed_at=ledger.executed_at,
            risk_result=None,
        )
        if ledger
        else None
    )
    risk_item = None
    risk = session.get(RiskResult, decision_id)
    if risk is not None:
        risk_item = RiskResultItem(
            decision_id=risk.decision_id,
            passed=risk.passed,
            reasons=list(risk.reasons or []),
            corrections=list(risk.corrections or []),
            evaluated_at=risk.evaluated_at,
        )
    llm_records = session.exec(
        select(LLMCallAudit).where(LLMCallAudit.decision_id == decision_id).order_by(LLMCallAudit.created_at.desc())
    ).all()
    llm_calls = [
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
        for record in llm_records
    ]
    status = ledger.status if ledger else DecisionStatus.DRAFT
    return DecisionDetailItem(
        decision_id=decision.decision_id,
        status=status,
        timestamp=decision.timestamp,
        observation_ref=decision.observation_id,
        actor_model=ledger.actor_model if ledger else decision.observation_id,
        checker_model=ledger.checker_model if ledger else decision.observation_id,
        notes=decision.notes,
        actions=actions,
        checker_result=checker_item,
        risk_result=risk_item,
        ledger=ledger_item,
        llm_calls=llm_calls,
    )
