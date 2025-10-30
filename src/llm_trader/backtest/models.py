"""回测领域模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    volume: int
    price: float
    created_at: datetime
    status: str = "created"
    filled_volume: int = 0
    filled_amount: float = 0.0


@dataclass
class Trade:
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    volume: int
    price: float
    fee: float
    tax: float
    timestamp: datetime


@dataclass
class Lot:
    volume: int
    cost_price: float
    acquired_at: datetime


@dataclass
class Position:
    symbol: str
    lots: List[Lot] = field(default_factory=list)
    frozen: bool = False

    @property
    def volume(self) -> int:
        return sum(lot.volume for lot in self.lots)

    @property
    def cost_price(self) -> float:
        total_volume = self.volume
        if total_volume == 0:
            return 0.0
        total_cost = sum(lot.cost_price * lot.volume for lot in self.lots)
        return total_cost / total_volume

    def add_lot(self, volume: int, price: float, acquired_at: datetime) -> None:
        self.lots.append(Lot(volume=volume, cost_price=price, acquired_at=acquired_at))

    def remove_volume(self, volume: int, before: Optional[datetime] = None) -> float:
        """移除指定数量的股票，返回对应的成本金额。

        参数：
            volume: 需要移除的股数。
            before: 仅允许出售 acquisition 时间早于 before 的仓位（用于 T+1）。
        """

        remaining = volume
        cost = 0.0
        new_lots: List[Lot] = []
        for lot in sorted(self.lots, key=lambda l: l.acquired_at):
            if before and lot.acquired_at >= before:
                new_lots.append(lot)
                continue
            if remaining <= 0:
                new_lots.append(lot)
                continue
            sell_vol = min(lot.volume, remaining)
            remaining -= sell_vol
            cost += lot.cost_price * sell_vol
            residual = lot.volume - sell_vol
            if residual > 0:
                new_lots.append(Lot(volume=residual, cost_price=lot.cost_price, acquired_at=lot.acquired_at))
        if remaining > 0:
            raise ValueError("可出售的持仓数量不足")
        self.lots = new_lots
        return cost

    def available_volume(self, before: Optional[datetime] = None) -> int:
        if before is None:
            return self.volume
        return sum(lot.volume for lot in self.lots if lot.acquired_at < before)

    def is_empty(self) -> bool:
        return not self.lots


@dataclass
class Account:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict[str, float]] = field(default_factory=list)

    def total_equity(self) -> float:
        if not self.equity_curve:
            return self.cash
        return self.equity_curve[-1]["equity"]

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]
