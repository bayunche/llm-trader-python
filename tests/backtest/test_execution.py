"""撮合引擎测试。"""

from __future__ import annotations

from datetime import datetime, timedelta

from llm_trader.backtest import Account, ExecutionConfig, ExecutionEngine, Order, OrderSide


def _price_lookup(prices):
    def lookup(symbol: str, _side: OrderSide) -> float:
        return prices[symbol]

    return lookup


def test_execute_buy_creates_position() -> None:
    account = Account(cash=100000.0)
    engine = ExecutionEngine()
    order = Order(
        order_id="1",
        symbol="600000.SH",
        side=OrderSide.BUY,
        volume=1000,
        price=10.0,
        created_at=datetime.utcnow(),
    )
    trades = engine.execute(account, [order], _price_lookup({"600000.SH": 10.0}), datetime(2024, 7, 1))
    assert len(trades) == 1
    assert account.positions["600000.SH"].volume == 1000
    assert account.cash < 100000.0
    assert order.status == "filled"


def test_execute_sell_with_t_plus_one() -> None:
    account = Account(cash=100000.0)
    engine = ExecutionEngine()
    buy_order = Order(
        order_id="b1",
        symbol="600000.SH",
        side=OrderSide.BUY,
        volume=1000,
        price=10.0,
        created_at=datetime.utcnow(),
    )
    engine.execute(account, [buy_order], _price_lookup({"600000.SH": 10.0}), datetime(2024, 7, 1))

    sell_order = Order(
        order_id="s1",
        symbol="600000.SH",
        side=OrderSide.SELL,
        volume=1000,
        price=11.0,
        created_at=datetime.utcnow(),
    )
    trades = engine.execute(account, [sell_order], _price_lookup({"600000.SH": 11.0}), datetime(2024, 7, 1))
    assert trades == []
    assert sell_order.status == "rejected"

    trades = engine.execute(account, [sell_order], _price_lookup({"600000.SH": 11.0}), datetime(2024, 7, 2))
    assert len(trades) == 1
    assert "600000.SH" not in account.positions
    assert sell_order.status == "filled"


def test_allow_same_day_sell_config() -> None:
    config = ExecutionConfig(allow_same_day_sell=True)
    engine = ExecutionEngine(config=config)
    account = Account(cash=100000.0)
    buy_order = Order(
        order_id="b2",
        symbol="000001.SZ",
        side=OrderSide.BUY,
        volume=100,
        price=10.0,
        created_at=datetime.utcnow(),
    )
    engine.execute(account, [buy_order], _price_lookup({"000001.SZ": 10.0}), datetime(2024, 7, 1))

    sell_order = Order(
        order_id="s2",
        symbol="000001.SZ",
        side=OrderSide.SELL,
        volume=100,
        price=10.5,
        created_at=datetime.utcnow(),
    )
    trades = engine.execute(account, [sell_order], _price_lookup({"000001.SZ": 10.5}), datetime(2024, 7, 1))
    assert len(trades) == 1
    assert "000001.SZ" not in account.positions
