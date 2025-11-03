"""默认 Mock 券商实现，立即按行情撮合。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

from llm_trader.backtest.models import Order, OrderSide, Trade

from .base import BrokerClient, BrokerConfig


class MockBrokerClient(BrokerClient):
    """基于行情价即时成交的模拟券商。"""

    def __init__(self, config: BrokerConfig, price_lookup) -> None:
        super().__init__(config)
        self._price_lookup = price_lookup

    def submit_orders(self, orders: Iterable[Order], dt: datetime) -> List[Trade]:
        trades: List[Trade] = []
        for order in orders:
            price = float(self._price_lookup(order.symbol, order.side))
            trade = Trade(
                trade_id=f"live-{order.order_id}",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                volume=order.volume,
                price=price,
                fee=0.0,
                tax=0.0,
                timestamp=dt,
            )
            trades.append(trade)
        return trades

    def sync_positions(self) -> None:  # pragma: no cover - mock 无需实现
        return None


__all__ = ["MockBrokerClient"]
