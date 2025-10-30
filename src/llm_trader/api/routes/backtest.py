"""回测 API 路由。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException

from llm_trader.api.responses import success_response
from llm_trader.api.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestResultPayload,
    BacktestTrade,
    EquityPoint,
)
from llm_trader.api.utils import load_ohlcv
from llm_trader.backtest import BacktestRunner, Order, OrderSide
from llm_trader.strategy import StrategyRepository, generate_orders_from_signals
from llm_trader.strategy.engine import RuleConfig, StrategyEngine

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _load_strategy_rules(strategy_id: str, version_id: Optional[str]) -> List[RuleConfig]:
    repository = StrategyRepository()
    versions = repository.list_versions(strategy_id)
    if not versions:
        raise HTTPException(status_code=404, detail={"error_code": "E-ST-404", "message": "策略版本不存在"})

    if version_id:
        matches = [v for v in versions if v.version_id == version_id]
        if not matches:
            raise HTTPException(status_code=404, detail={"error_code": "E-ST-404", "message": "策略版本不存在"})
        selected = matches[0]
    else:
        selected = versions[-1]

    rules: List[RuleConfig] = []
    for rule in selected.rules:
        rules.append(
            RuleConfig(
                indicator=rule.get("indicator"),
                column=rule.get("column"),
                params=rule.get("params", {}),
                operator=rule.get("operator"),
                threshold=rule.get("threshold"),
            )
        )
    return rules


def _prepare_orders(bars: List[Dict[str, object]], rules: List[RuleConfig]) -> Dict[datetime, List[Order]]:
    df = pd.DataFrame(bars)
    df["dt"] = pd.to_datetime(df["dt"])
    df.sort_values("dt", inplace=True)
    orders_by_date: Dict[datetime, List[Order]] = defaultdict(list)

    for symbol, group in df.groupby("symbol"):
        group = group.set_index("dt").sort_index()
        engine = StrategyEngine(rules)
        evaluated = engine.evaluate(group)
        evaluated["symbol"] = symbol
        orders = generate_orders_from_signals(evaluated, symbol=symbol)
        for order in orders:
            orders_by_date[order.created_at].append(order)

    return orders_by_date


@router.post("/run", response_model=BacktestResponse, summary="触发回测")
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    bars = load_ohlcv(request.symbols, "D", request.start_date, request.end_date)
    if not bars:
        raise HTTPException(status_code=404, detail={"error_code": "E-DS-404", "message": "行情数据缺失"})

    try:
        rules = _load_strategy_rules(request.strategy_id, request.run_id)
    except HTTPException:
        raise

    orders_by_date = _prepare_orders(bars, rules)

    runner = BacktestRunner(initial_cash=request.initial_cash)

    def signal_provider(dt: datetime, *_args) -> List[Order]:
        return orders_by_date.get(dt, [])

    result = runner.run(
        bars,
        signal_provider,
        strategy_id=request.strategy_id,
        run_id=request.run_id,
        persist=True,
    )

    trades_payload = [
        BacktestTrade(
            trade_id=trade.trade_id,
            order_id=trade.order_id,
            symbol=trade.symbol,
            side=trade.side.value,
            volume=trade.volume,
            price=trade.price,
            fee=trade.fee,
            tax=trade.tax,
            timestamp=trade.timestamp,
        )
        for trade in result.trades
    ]

    equity_curve = [
        EquityPoint(date=point.get("date"), equity=point.get("equity"))
        for point in result.equity_curve
    ]

    run_identifier = request.run_id or (
        result.storage_paths.get("equity").stem if result.storage_paths else "runtime"
    )

    payload = BacktestResultPayload(
        run_id=run_identifier,
        metrics=result.metrics,
        equity_curve=equity_curve,
        trades=trades_payload,
    )
    return success_response(payload)
