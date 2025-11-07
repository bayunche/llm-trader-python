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

from .execution_adapters import ExecutionAdapter, SandboxExecutionAdapter
from .brokers.base import BrokerClient


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
        adapter: Optional[ExecutionAdapter] = None,
    ) -> None:
        self.config = config
        self.account = Account(cash=config.initial_cash)
        self.repository = repository or ParquetRepository()
        self.execution_engine = ExecutionEngine(execution_config)
        self.adapter = adapter or SandboxExecutionAdapter()

    def execute(
        self,
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: PriceLookup,
    ) -> List[Trade]:
        """执行订单并记录订单、成交及账户权益。"""
        from .execution_adapters import LiveBrokerExecutionAdapter  # 延迟导入防循环

        if isinstance(self.adapter, LiveBrokerExecutionAdapter):
            raise NotImplementedError("当前环境未启用实盘执行，请使用 sandbox 模式")
        return self.adapter.execute(self, dt, orders, price_lookup)

    def _execute_sandbox(
        self,
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: PriceLookup,
    ) -> List[Trade]:
        """沙盒执行路径，复用本地撮合引擎。"""

        trades = self.execution_engine.execute(self.account, orders, price_lookup, dt)
        self._record(dt, orders, trades, price_lookup)
        return trades

    def _execute_live(
        self,
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: PriceLookup,
        broker_client: BrokerClient,
    ) -> List[Trade]:
        """实盘执行路径，委托给券商客户端。"""

        trades = broker_client.submit_orders(orders, dt)
        self._settle_trades(orders, trades, dt)
        self._record(dt, orders, trades, price_lookup)
        broker_client.sync_positions()
        return trades

    def _settle_trades(
        self,
        orders: Sequence[Order],
        trades: Sequence[Trade],
        trading_dt: datetime,
    ) -> None:
        order_map = {order.order_id: order for order in orders}
        for trade in trades:
            order = order_map.get(trade.order_id)
            if order:
                order.status = "filled"
                order.filled_volume = trade.volume
                order.filled_amount = trade.price * trade.volume
            if trade.side == OrderSide.BUY:
                total_cost = trade.price * trade.volume + trade.fee + trade.tax
                self.account.cash -= total_cost
                position = self.account.get_position(trade.symbol)
                position.add_lot(trade.volume, trade.price, trading_dt)
            else:
                position = self.account.positions.get(trade.symbol)
                if position:
                    proceeds = trade.price * trade.volume - trade.fee - trade.tax
                    allowed_before = trading_dt
                    position.remove_volume(trade.volume, before=allowed_before)
                    self.account.cash += proceeds
                    if position.is_empty():
                        del self.account.positions[trade.symbol]
                else:
                    self.account.cash += trade.price * trade.volume - trade.fee - trade.tax
            self.account.trades.append(trade)

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
