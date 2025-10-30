"""信号转订单工具。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List

import pandas as pd

from llm_trader.backtest import Order, OrderSide


def generate_orders_from_signals(
    df: pd.DataFrame,
    *,
    symbol: str,
    lot_size: int = 100,
    volume_per_trade: int = 100,
) -> List[Order]:
    orders: List[Order] = []
    for dt, row in df.iterrows():
        signal = int(row.get("signal", 0))
        if signal == 1:
            orders.append(
                Order(
                    order_id=f"buy-{dt.isoformat()}",
                    symbol=symbol,
                    side=OrderSide.BUY,
                    volume=max(volume_per_trade // lot_size, 1) * lot_size,
                    price=float(row.get("open", row.get("close", 0.0))),
                    created_at=dt if isinstance(dt, datetime) else datetime.fromisoformat(str(dt)),
                )
            )
        elif signal == -1:
            orders.append(
                Order(
                    order_id=f"sell-{dt.isoformat()}",
                    symbol=symbol,
                    side=OrderSide.SELL,
                    volume=max(volume_per_trade // lot_size, 1) * lot_size,
                    price=float(row.get("open", row.get("close", 0.0))),
                    created_at=dt if isinstance(dt, datetime) else datetime.fromisoformat(str(dt)),
                )
            )
    return orders
