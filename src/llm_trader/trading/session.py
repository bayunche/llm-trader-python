"""自动交易会话管理。

该模块封装了账户状态、撮合执行与交易日志记录，复用回测模块的撮合引擎，
为后续实时行情→策略→下单的自动化流程提供基础能力。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence

from llm_trader.backtest.execution import ExecutionConfig, ExecutionEngine
from llm_trader.backtest.models import Account, Order, OrderSide, Position, Trade
from llm_trader.data.repositories.parquet import ParquetRepository


PriceLookup = Callable[[str, OrderSide], float]


@dataclass
class TradingSessionConfig:
    """交易会话配置。"""

    session_id: str
    strategy_id: str
    initial_cash: float = 1_000_000.0


class TradingSession:
    """封装单次交易会话的执行与记录逻辑。"""

    def __init__(
        self,
        config: TradingSessionConfig,
        *,
        repository: Optional[ParquetRepository] = None,
        execution_config: Optional[ExecutionConfig] = None,
    ) -> None:
        self.config = config
        self.account = Account(cash=config.initial_cash)
        self.repository = repository or ParquetRepository()
        self.execution_engine = ExecutionEngine(execution_config)

    def execute(
        self,
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: PriceLookup,
    ) -> List[Trade]:
        """执行订单并记录订单、成交及账户权益。"""

        trades = self.execution_engine.execute(self.account, orders, price_lookup, dt)
        self._record(dt, orders, trades, price_lookup)
        return trades

    def _record(
        self,
        dt: datetime,
        orders: Sequence[Order],
        trades: Sequence[Trade],
        price_lookup: PriceLookup,
    ) -> None:
        orders_payload = [
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "volume": order.volume,
                "price": order.price,
                "status": order.status,
                "filled_volume": order.filled_volume,
                "filled_amount": order.filled_amount,
                "created_at": order.created_at,
            }
            for order in orders
        ]
        self.repository.write_trading_orders(
            self.config.session_id,
            self.config.strategy_id,
            dt,
            orders_payload,
        )

        trades_payload = [
            {
                "trade_id": trade.trade_id,
                "order_id": trade.order_id,
                "symbol": trade.symbol,
                "side": trade.side.value,
                "volume": trade.volume,
                "price": trade.price,
                "fee": trade.fee,
                "tax": trade.tax,
                "timestamp": trade.timestamp,
            }
            for trade in trades
        ]
        self.repository.write_trading_trades(
            self.config.session_id,
            self.config.strategy_id,
            dt,
            trades_payload,
        )

        snapshot = {
            "timestamp": dt,
            "cash": self.account.cash,
            "equity": self._compute_equity(price_lookup),
            "positions": json.dumps(self._serialize_positions()),
        }
        self.account.equity_curve.append({"date": dt, "equity": snapshot["equity"]})
        self.repository.write_trading_equity(
            self.config.session_id,
            self.config.strategy_id,
            snapshot,
        )

    def snapshot_positions(self) -> List[Dict[str, object]]:
        """返回当前持仓的结构化快照。"""

        payload: List[Dict[str, object]] = []
        for symbol, position in self.account.positions.items():
            if position.volume == 0:
                continue
            payload.append(
                {
                    "symbol": symbol,
                    "volume": position.volume,
                    "cost_price": position.cost_price,
                    "lots": [
                        {
                            "volume": lot.volume,
                            "cost_price": lot.cost_price,
                            "acquired_at": lot.acquired_at,
                        }
                        for lot in position.lots
                    ],
                }
            )
        return payload

    def _serialize_positions(self) -> List[dict]:
        """序列化当前持仓信息，便于写入日志。"""

        payload: List[dict] = []
        for symbol, position in self.account.positions.items():
            if position.volume == 0:
                continue
            payload.append(
                {
                    "symbol": symbol,
                    "volume": position.volume,
                    "cost_price": position.cost_price,
                    "lots": [
                        {
                            "volume": lot.volume,
                            "cost_price": lot.cost_price,
                            "acquired_at": lot.acquired_at.isoformat(),
                        }
                        for lot in position.lots
                    ],
                }
            )
        return payload

    def _compute_equity(self, price_lookup: PriceLookup) -> float:
        """根据账户现金与持仓估算权益。"""

        equity = self.account.cash
        for symbol, position in self.account.positions.items():
            if position.volume == 0:
                continue
            price = self._safe_price_lookup(price_lookup, symbol, position)
            equity += position.volume * price
        return float(equity)

    @staticmethod
    def _safe_price_lookup(price_lookup: PriceLookup, symbol: str, position: Position) -> float:
        """获取持仓估值价格，失败时回退至成本价。"""

        try:
            return float(price_lookup(symbol, OrderSide.SELL))
        except Exception:  # pragma: no cover - 极端场景兜底
            return float(position.cost_price)
