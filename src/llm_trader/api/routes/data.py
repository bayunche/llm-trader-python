"""数据相关 API 路由。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Query

from llm_trader.api.responses import success_response
from llm_trader.api.schemas import (
    OhlcvItem,
    OhlcvResponse,
    PaginationMeta,
    SymbolsResponse,
    SymbolItem,
)
from llm_trader.api.utils import load_ohlcv, load_symbols

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/symbols", response_model=SymbolsResponse, summary="获取证券列表")
async def list_symbols() -> SymbolsResponse:
    df = load_symbols()
    items: List[SymbolItem] = []
    for _, row in df.iterrows():
        items.append(
            SymbolItem(
                symbol=row.get("symbol", ""),
                name=row.get("name", ""),
                board=row.get("board", ""),
                status=row.get("status", ""),
                listed_date=row.get("listed_date"),
                delisted_date=row.get("delisted_date"),
            )
        )
    meta = PaginationMeta(total=len(items), page=1, size=len(items) or 1) if items else None
    return success_response(data=items, meta=meta)

@router.get("/ohlcv", response_model=OhlcvResponse, summary="查询行情数据")
async def list_ohlcv(
    symbol: str = Query(..., description="证券代码"),
    freq: str = Query("D", description="数据频率"),
    start: Optional[datetime] = Query(None, description="开始时间"),
    end: Optional[datetime] = Query(None, description="结束时间"),
) -> OhlcvResponse:
    raw_records = load_ohlcv([symbol], freq, start, end)
    items = [
        OhlcvItem(
            symbol=record.get("symbol", symbol),
            dt=record.get("dt"),
            freq=record.get("freq", freq),
            open=record.get("open"),
            high=record.get("high"),
            low=record.get("low"),
            close=record.get("close"),
            volume=record.get("volume"),
            amount=record.get("amount"),
        )
        for record in raw_records
    ]
    meta = PaginationMeta(total=len(items), page=1, size=len(items) or 1)
    return success_response(data=items, meta=meta)
