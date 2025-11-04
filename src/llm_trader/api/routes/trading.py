"""交易数据查询 API。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from llm_trader.api.responses import success_response
from llm_trader.api.schemas import (
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
