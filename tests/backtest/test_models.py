"""回测模型单元测试。"""

from __future__ import annotations

from datetime import datetime

from llm_trader.backtest import Account, Order, OrderSide


def test_account_equity_curve_default() -> None:
    account = Account(cash=100000.0)
    assert account.total_equity() == 100000.0


def test_order_defaults() -> None:
    order = Order(
        order_id="1",
        symbol="600000.SH",
        side=OrderSide.BUY,
        volume=1000,
        price=10.0,
        created_at=datetime.utcnow(),
    )
    assert order.status == "created"
    assert order.filled_volume == 0
