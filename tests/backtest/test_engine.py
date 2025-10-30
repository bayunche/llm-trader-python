"""回测运行流程测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from llm_trader.backtest import BacktestRunner, Order, OrderSide
from llm_trader.data import default_manager
from llm_trader.data.repositories.parquet import ParquetRepository


def _simple_signal(first_buy_date: datetime, sell_date: datetime):
    def signal_provider(dt: datetime, bars: Dict[str, Dict], account):
        orders = []
        if dt == first_buy_date and "600000.SH" not in account.positions:
            orders.append(
                Order(
                    order_id="buy",
                    symbol="600000.SH",
                    side=OrderSide.BUY,
                    volume=1000,
                    price=float(bars["600000.SH"]["open"]),
                    created_at=dt,
                )
            )
        if dt == sell_date:
            orders.append(
                Order(
                    order_id="sell",
                    symbol="600000.SH",
                    side=OrderSide.SELL,
                    volume=1000,
                    price=float(bars["600000.SH"]["open"]),
                    created_at=dt,
                )
            )
        return orders

    return signal_provider


def test_backtest_runner_generates_equity_curve(tmp_path) -> None:
    bars = [
        {"dt": datetime(2024, 7, 1), "symbol": "600000.SH", "open": 10.0, "close": 10.5},
        {"dt": datetime(2024, 7, 2), "symbol": "600000.SH", "open": 10.6, "close": 10.8},
        {"dt": datetime(2024, 7, 3), "symbol": "600000.SH", "open": 10.9, "close": 10.7},
    ]
    manager = default_manager(base_dir=tmp_path)
    repository = ParquetRepository(manager=manager)
    runner = BacktestRunner(initial_cash=100000.0, repository=repository)
    result = runner.run(
        bars,
        _simple_signal(datetime(2024, 7, 1), datetime(2024, 7, 3)),
        strategy_id="demo",
        run_id="unit-test",
    )
    assert len(result.equity_curve) == 3
    # 第三日卖出后仓位应归零
    assert "600000.SH" not in result.account.positions or result.account.positions["600000.SH"].volume == 0
    assert result.trades[-1].side == OrderSide.SELL
    assert "total_return" in result.metrics
    assert "equity" in result.storage_paths
    assert result.storage_paths["equity"].exists()
