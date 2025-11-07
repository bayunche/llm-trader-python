"""API 路由入口。"""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends

from llm_trader.api.security import require_api_key

from .backtest import router as backtest_router
from .config_models import router as config_models_router
from .monitoring import router as monitoring_router
from .data import router as data_router
from .strategy import router as strategy_router
from .trading import router as trading_router

router = APIRouter()
router.include_router(data_router, dependencies=[Depends(require_api_key)])
router.include_router(backtest_router, dependencies=[Depends(require_api_key)])
router.include_router(strategy_router, dependencies=[Depends(require_api_key)])
router.include_router(trading_router)
router.include_router(config_models_router, dependencies=[Depends(require_api_key)])
router.include_router(monitoring_router, dependencies=[Depends(require_api_key)])


@router.get("/health", summary="服务健康检查")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}
