"""回测执行引擎。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Union
from uuid import uuid4

from llm_trader.backtest.execution import ExecutionConfig, ExecutionEngine
from llm_trader.backtest.metrics import compute_metrics
from llm_trader.backtest.models import Account, Order, OrderSide
from llm_trader.data.repositories.parquet import ParquetRepository

Bar = Dict[str, Union[float, datetime, str]]


@dataclass
class BacktestResult:
    account: Account
    trades: List
    equity_curve: List[Dict[str, float]]
    metrics: Dict[str, float]
    storage_paths: Dict[str, Path]


SignalProvider = Callable[[datetime, Dict[str, Bar], Account], Sequence[Order]]


class BacktestRunner:
    def __init__(
        self,
        *,
        initial_cash: float = 1_000_000.0,
        execution_config: ExecutionConfig | None = None,
        repository: ParquetRepository | None = None,
    ) -> None:
        self.initial_cash = initial_cash
        self.execution_engine = ExecutionEngine(execution_config)
        self.repository = repository or ParquetRepository()

    def run(
        self,
        bars: Iterable[Bar],
        signal_provider: SignalProvider,
        *,
        strategy_id: str = "default",
        run_id: str | None = None,
        persist: bool = True,
    ) -> BacktestResult:
        grouped = defaultdict(dict)
        for bar in bars:
            dt = bar["dt"]
            if isinstance(dt, str):
                dt = datetime.fromisoformat(dt)
            grouped[dt][bar["symbol"]] = bar

        dates = sorted(grouped.keys())
        account = Account(cash=self.initial_cash)
        all_trades: List = []

        for dt in dates:
            symbols = grouped[dt]
            orders = signal_provider(dt, symbols, account)

            def price_lookup(symbol: str, _side: OrderSide) -> float:
                return float(symbols[symbol]["open"])  # 次日开盘价成交模型

            trades = self.execution_engine.execute(account, orders, price_lookup, dt)
            all_trades.extend(trades)

            equity = account.cash
            for symbol, position in list(account.positions.items()):
                if position.is_empty():
                    account.positions.pop(symbol, None)
                    continue
                close_price = float(symbols.get(symbol, {}).get("close", price_lookup(symbol, OrderSide.BUY)))
                equity += position.volume * close_price
            account.equity_curve.append({"date": dt, "equity": equity})

        metrics = compute_metrics(account.equity_curve)
        run_identifier = run_id or f"run-{uuid4().hex[:8]}"
        run_date = dates[-1] if dates else datetime.utcnow()
        storage_paths: Dict[str, Path] = {}

        if persist:
            equity_records = account.equity_curve
            trades_records = [
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
                for trade in all_trades
            ]
            storage_paths = self.repository.write_backtest_result(
                strategy_id=strategy_id,
                run_id=run_identifier,
                run_date=run_date,
                equity_curve=equity_records,
                trades=trades_records,
            )

        return BacktestResult(
            account=account,
            trades=all_trades,
            equity_curve=account.equity_curve,
            metrics=metrics,
            storage_paths=storage_paths,
        )
