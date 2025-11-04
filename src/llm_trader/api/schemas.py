"""API 数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    size: int = Field(ge=1)


class APIResponse(BaseModel, Generic[T]):
    code: str = Field(default="OK")
    message: str = Field(default="success")
    data: Optional[T] = None
    meta: Optional[PaginationMeta] = None


class SymbolItem(BaseModel):
    symbol: str
    name: str
    board: str
    status: str
    listed_date: Optional[datetime]
    delisted_date: Optional[datetime]


class SymbolsResponse(APIResponse[List[SymbolItem]]):
    pass


class BacktestRequest(BaseModel):
    strategy_id: str
    run_id: Optional[str]
    symbols: List[str]
    start_date: datetime
    end_date: datetime
    initial_cash: float = Field(gt=0)


class BacktestMetric(BaseModel):
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float


class BacktestTrade(BaseModel):
    trade_id: str
    order_id: str
    symbol: str
    side: str
    volume: int
    price: float
    fee: float
    tax: float
    timestamp: datetime


class EquityPoint(BaseModel):
    date: datetime
    equity: float


class BacktestResultPayload(BaseModel):
    run_id: str
    metrics: BacktestMetric
    equity_curve: List[EquityPoint]
    trades: List[BacktestTrade]


class BacktestResponse(APIResponse[BacktestResultPayload]):
    pass


class StrategyVersionPayload(BaseModel):
    strategy_id: str
    version_id: str
    run_id: str
    created_at: datetime
    metrics: BacktestMetric


class StrategyVersionResponse(APIResponse[List[StrategyVersionPayload]]):
    pass


class OhlcvItem(BaseModel):
    symbol: str
    dt: datetime
    freq: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class OhlcvResponse(APIResponse[List[OhlcvItem]]):
    pass


class TradingOrderItem(BaseModel):
    order_id: str
    symbol: str
    side: str
    volume: int
    price: float
    status: str
    filled_volume: int
    filled_amount: float
    created_at: datetime


class TradingTradeItem(BaseModel):
    trade_id: str
    order_id: str
    symbol: str
    side: str
    volume: int
    price: float
    fee: float
    tax: float
    timestamp: datetime


class TradingEquityItem(BaseModel):
    timestamp: datetime
    cash: float
    equity: float
    positions: Optional[List[Dict[str, object]]] = None


class TradingLogItem(BaseModel):
    timestamp: datetime
    prompt: str
    response: str
    suggestion_description: Optional[str] = None
    objective: Optional[str] = None
    symbols: Optional[List[str]] = None
    indicators: Optional[List[str]] = None
    quotes_summary: Optional[str] = None


class TradingOrderResponse(APIResponse[List[TradingOrderItem]]):
    pass


class TradingTradeResponse(APIResponse[List[TradingTradeItem]]):
    pass


class TradingEquityResponse(APIResponse[List[TradingEquityItem]]):
    pass


class TradingLogResponse(APIResponse[List[TradingLogItem]]):
    pass


class TradingRunHistoryItem(BaseModel):
    timestamp: datetime
    status: str
    decision_proceed: bool
    alerts: List[str] = Field(default_factory=list)
    orders_executed: int = 0
    trades_filled: int = 0
    selected_symbols: List[str] = Field(default_factory=list)
    suggestion_description: Optional[str] = None
    rules: List[Dict[str, object]] = Field(default_factory=list)
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    objective: Optional[str] = None
    indicators: List[str] = Field(default_factory=list)
    strategy_id: Optional[str] = None
    session_id: Optional[str] = None


class TradingRunHistoryResponse(APIResponse[List[TradingRunHistoryItem]]):
    pass
