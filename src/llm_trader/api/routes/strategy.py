"""策略相关 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from llm_trader.api.responses import success_response
from llm_trader.api.schemas import BacktestMetric, StrategyVersionPayload, StrategyVersionResponse
from llm_trader.strategy import StrategyRepository

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/versions", response_model=StrategyVersionResponse, summary="策略版本列表")
async def list_strategy_versions(strategy_id: str = Query(..., description="策略 ID")) -> StrategyVersionResponse:
    repository = StrategyRepository()
    versions = repository.list_versions(strategy_id)
    payload = []
    for v in versions:
        metrics = v.metrics or {}
        payload.append(
            StrategyVersionPayload(
                strategy_id=v.strategy_id,
                version_id=v.version_id,
                run_id=v.run_id,
                created_at=v.created_at,
                metrics=BacktestMetric(
                    total_return=metrics.get("total_return", 0.0),
                    annual_return=metrics.get("annual_return", 0.0),
                    max_drawdown=metrics.get("max_drawdown", 0.0),
                    sharpe_ratio=metrics.get("sharpe_ratio", 0.0),
                ),
            )
        )
    return success_response(data=payload)
