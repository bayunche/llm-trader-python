"""Live 模式执行适配器测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.backtest.models import Order, OrderSide
from llm_trader.data import default_manager
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.trading.brokers.base import BrokerConfig
from llm_trader.trading.execution_adapters import LiveBrokerExecutionAdapter
from llm_trader.trading.session import TradingSession, TradingSessionConfig


def _price_lookup(_symbol: str, side: OrderSide) -> float:
    return 10.0 if side == OrderSide.BUY else 9.5


def test_live_adapter_with_mock_broker(tmp_path) -> None:
    manager = default_manager(base_dir=tmp_path / "data_store")
    session = TradingSession(
        TradingSessionConfig(session_id="live-session", strategy_id="live-strategy"),
        repository=ParquetRepository(manager=manager),
    )

    adapter = LiveBrokerExecutionAdapter(
        BrokerConfig(provider="mock", account="demo-account")
    )

    order = Order(
        order_id="order-1",
        symbol="600000.SH",
        side=OrderSide.BUY,
        volume=100,
        price=10.0,
        created_at=datetime.utcnow(),
    )

    trades = adapter.execute(session, datetime.utcnow(), [order], _price_lookup)

    assert len(trades) == 1
    assert trades[0].price == 10.0
    assert session.account.positions["600000.SH"].volume == 100
