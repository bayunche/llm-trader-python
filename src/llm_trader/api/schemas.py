"""API 数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field
from llm_trader.db.models.enums import DecisionStatus, ModelRole

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


class ModelEndpointItem(BaseModel):
    model_alias: str
    provider: str
    endpoint_url: str
    auth_type: str
    auth_secret_ref: str
    weight: float
    timeout: float
    max_retries: int
    enabled: bool
    default_params: Dict[str, Any]
    headers: Dict[str, Any]
    circuit_breaker: Dict[str, Any]
    prompt_cost_per_1k: float
    completion_cost_per_1k: float
    created_at: datetime
    updated_at: datetime


class ModelEndpointListResponse(APIResponse[List[ModelEndpointItem]]):
    pass


class ModelEndpointResponse(APIResponse[ModelEndpointItem]):
    pass


class ModelEndpointMetric(BaseModel):
    endpoint: str
    enabled: bool
    available: bool
    success_count: int
    failure_count: int
    consecutive_failures: int
    opened_until: Optional[datetime]
    last_error: Optional[str]


class ModelEndpointMetricsResponse(APIResponse[List[ModelEndpointMetric]]):
    pass


ModelEndpointListResponse.model_rebuild()
ModelEndpointResponse.model_rebuild()
ModelEndpointMetricsResponse.model_rebuild()


class LLMCallAuditItem(BaseModel):
    trace_id: str
    decision_id: Optional[str] = None
    role: ModelRole
    provider: str
    model: str
    tokens_prompt: int
    tokens_completion: int
    latency_ms: int
    cost: float
    created_at: datetime


class LLMCallAuditResponse(APIResponse[List[LLMCallAuditItem]]):
    pass


class RiskResultItem(BaseModel):
    decision_id: str
    passed: bool
    reasons: List[str] = Field(default_factory=list)
    corrections: List[str] = Field(default_factory=list)
    evaluated_at: datetime


class DecisionLedgerItem(BaseModel):
    decision_id: str
    status: DecisionStatus
    observation_ref: str
    actor_model: str
    checker_model: str
    risk_summary: Dict[str, Any]
    created_at: datetime
    executed_at: Optional[datetime] = None
    risk_result: Optional[RiskResultItem] = None


class DecisionLedgerResponse(APIResponse[List[DecisionLedgerItem]]):
    pass


class DecisionActionItem(BaseModel):
    type: str
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    price: Optional[float] = None
    qty: Optional[int] = None
    tif: Optional[str] = None
    target_order_id: Optional[str] = None


class CheckerResultItem(BaseModel):
    status: str
    reasons: List[str] = Field(default_factory=list)
    observation_expired: bool = False
    checked_at: datetime


class DecisionDetailItem(BaseModel):
    decision_id: str
    status: DecisionStatus
    timestamp: datetime
    observation_ref: str
    actor_model: str
    checker_model: str
    notes: Optional[str] = None
    actions: List[DecisionActionItem] = Field(default_factory=list)
    checker_result: Optional[CheckerResultItem] = None
    risk_result: Optional[RiskResultItem] = None
    ledger: Optional[DecisionLedgerItem] = None
    llm_calls: List[LLMCallAuditItem] = Field(default_factory=list)


class DecisionDetailResponse(APIResponse[DecisionDetailItem]):
    pass
