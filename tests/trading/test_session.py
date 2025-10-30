"""交易会话执行测试。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from llm_trader.backtest.models import Order, OrderSide
from llm_trader.data import DatasetKind, default_manager
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.trading import TradingSession, TradingSessionConfig


def _build_session(tmp_path: Path) -> TradingSession:
    base_dir = tmp_path / "data_store"
    manager = default_manager(base_dir=base_dir)
    repository = ParquetRepository(manager=manager)
    config = TradingSessionConfig(session_id="demo-session", strategy_id="demo-strategy", initial_cash=100000.0)
    return TradingSession(config, repository=repository)


def test_trading_session_executes_and_persists(tmp_path: Path) -> None:
    session = _build_session(tmp_path)
    dt = datetime(2024, 1, 2, 9, 30)
    order = Order(
        order_id="order-1",
        symbol="600000.SH",
        side=OrderSide.BUY,
        volume=100,
        price=10.0,
        created_at=dt,
    )

    def price_lookup(symbol: str, _side: OrderSide) -> float:
        assert symbol == "600000.SH"
        return 10.0

    trades = session.execute(dt, [order], price_lookup)
    assert len(trades) == 1
    # 成交后仓位应存在
    assert session.account.positions["600000.SH"].volume == 100

    manager = session.repository.manager
    orders_path = manager.path_for(
        DatasetKind.TRADING_ORDERS,
        symbol="demo-session",
        freq="demo-strategy",
        timestamp=dt,
    )
    trades_path = manager.path_for(
        DatasetKind.TRADING_TRADES,
        symbol="demo-session",
        freq="demo-strategy",
        timestamp=dt,
    )
    equity_path = manager.path_for(
        DatasetKind.TRADING_EQUITY,
        symbol="demo-session",
        freq="demo-strategy",
        timestamp=dt,
    )

    orders_df = pd.read_parquet(orders_path)
    trades_df = pd.read_parquet(trades_path)
    equity_df = pd.read_parquet(equity_path)

    assert orders_df.iloc[0]["order_id"] == "order-1"
    assert trades_df.iloc[0]["trade_id"] == "trade-order-1"

    positions_payload = json.loads(equity_df.iloc[-1]["positions"])
    assert positions_payload[0]["symbol"] == "600000.SH"
    assert session.account.cash < 100000.0
