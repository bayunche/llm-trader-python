"""撮合执行逻辑骨架。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, List

from llm_trader.backtest.models import Account, Order, OrderSide, Trade


@dataclass
class ExecutionConfig:
    commission_rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.001
    transfer_fee_rate: float = 0.00002
    allow_same_day_sell: bool = False


class ExecutionEngine:
    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config or ExecutionConfig()

    def execute(
        self,
        account: Account,
        orders: Iterable[Order],
        price_lookup: Callable[[str, OrderSide], float],
        trading_dt: datetime,
    ) -> List[Trade]:
        trades: List[Trade] = []
        for order in orders:
            price = price_lookup(order.symbol, order.side)
            if price <= 0:
                continue
            if order.side == OrderSide.BUY:
                trade = self._execute_buy(account, order, price, trading_dt)
            else:
                trade = self._execute_sell(account, order, price, trading_dt)
            if trade:
                trades.append(trade)
        return trades

    def _execute_buy(self, account: Account, order: Order, price: float, trading_dt: datetime) -> Trade | None:
        commission = max(price * order.volume * self.config.commission_rate, self.config.min_commission)
        transfer_fee = price * order.volume * self.config.transfer_fee_rate
        total_cost = price * order.volume + commission + transfer_fee
        if account.cash < total_cost:
            order.status = "rejected"
            return None

        account.cash -= total_cost
        position = account.get_position(order.symbol)
        position.add_lot(order.volume, price, trading_dt)

        trade = Trade(
            trade_id=f"trade-{order.order_id}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            price=price,
            fee=commission + transfer_fee,
            tax=0.0,
            timestamp=trading_dt,
        )
        account.trades.append(trade)

        order.status = "filled"
        order.filled_volume = order.volume
        order.filled_amount = price * order.volume
        return trade

    def _execute_sell(self, account: Account, order: Order, price: float, trading_dt: datetime) -> Trade | None:
        position = account.positions.get(order.symbol)
        if not position:
            order.status = "rejected"
            return None

        allowed_before = None if self.config.allow_same_day_sell else trading_dt
        available_volume = position.available_volume(before=allowed_before)
        if available_volume < order.volume:
            order.status = "rejected"
            return None

        commission = max(price * order.volume * self.config.commission_rate, self.config.min_commission)
        transfer_fee = price * order.volume * self.config.transfer_fee_rate
        stamp_duty = price * order.volume * self.config.stamp_duty_rate

        position.remove_volume(order.volume, before=allowed_before)
        proceeds = price * order.volume
        account.cash += proceeds - commission - transfer_fee - stamp_duty

        if position.is_empty():
            del account.positions[order.symbol]

        trade = Trade(
            trade_id=f"trade-{order.order_id}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            volume=order.volume,
            price=price,
            fee=commission + transfer_fee,
            tax=stamp_duty,
            timestamp=trading_dt,
        )
        account.trades.append(trade)

        order.status = "filled"
        order.filled_volume = order.volume
        order.filled_amount = proceeds
        return trade
