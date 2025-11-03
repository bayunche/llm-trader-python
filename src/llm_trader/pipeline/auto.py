"""全链路自动交易管道。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from llm_trader.api.utils import load_ohlcv
from llm_trader.backtest import BacktestRunner, Order
from llm_trader.backtest.models import OrderSide
from llm_trader.config import get_settings
from llm_trader.common import get_logger
from llm_trader.reports import ReportBuilder, ReportPayload, ReportWriter, load_report_payload
from llm_trader.trading import TradingCycleConfig, run_managed_trading_cycle
from llm_trader.trading.manager import ManagedTradingResult
from llm_trader.strategy import generate_orders_from_signals
from llm_trader.strategy.engine import RuleConfig, StrategyEngine
from llm_trader.trading.orchestrator import run_ai_trading_cycle

_LOGGER = get_logger("pipeline.auto")


@dataclass
class BacktestCriteria:
    """回测验收标准。"""

    min_total_return: float = field(
        default_factory=lambda: get_settings().trading.backtest_min_return
    )
    max_drawdown: float = field(
        default_factory=lambda: get_settings().trading.backtest_max_drawdown
    )


@dataclass
class AutoTradingConfig:
    """全链路自动交易配置。"""

    trading: TradingCycleConfig
    backtest_start: datetime
    backtest_end: datetime
    criteria: BacktestCriteria = field(default_factory=BacktestCriteria)
    run_backtest: bool = field(default_factory=lambda: get_settings().trading.run_backtest)


@dataclass
class AutoTradingResult:
    status: str
    backtest_metrics: Optional[Dict[str, float]]
    managed_result: Optional[ManagedTradingResult]
    report_paths: Optional[Dict[str, Path]]


def run_full_automation(
    config: AutoTradingConfig,
    *,
    trading_session=None,
    load_ohlcv_fn=load_ohlcv,
) -> AutoTradingResult:
    """执行从策略生成到风险控制的全链路流程。"""

    trading_result = run_ai_trading_cycle(config.trading, trading_session=trading_session)
    suggestion = trading_result["suggestion"]
    derived_config: TradingCycleConfig = trading_result.get("config", config.trading)

    backtest_metrics: Optional[Dict[str, float]] = None

    if config.run_backtest:
        bars = load_ohlcv_fn(
            derived_config.symbols,
            derived_config.freq,
            config.backtest_start,
            config.backtest_end,
        )
        if not bars:
            return AutoTradingResult("backtest_missing_data", None, None, None)

        runner = BacktestRunner()
        orders_by_date = _prepare_orders_for_backtest(bars, suggestion.rules)

        def provider(dt: datetime, *_args) -> List[Order]:
            return orders_by_date.get(dt, [])

        result = runner.run(
            bars,
            provider,
            strategy_id=derived_config.strategy_id,
            run_id="auto",
            persist=False,
        )
        backtest_metrics = result.metrics
        if not _pass_criteria(backtest_metrics, config.criteria):
            return AutoTradingResult("backtest_rejected", backtest_metrics, None, None)

    managed = run_managed_trading_cycle(
        derived_config,
        trading_session=trading_result["session"],
    )
    status = "executed" if managed.decision.proceed else "risk_blocked"
    report_paths: Optional[Dict[str, Path]] = None
    try:
        report_paths = _generate_reports(
            derived_config,
            trading_result,
            managed,
            backtest_metrics or {},
        )
    except Exception as exc:  # pragma: no cover - 生成报表失败时仅记录
        _LOGGER.warning("报表生成失败", extra={"error": str(exc)})
    return AutoTradingResult(status, backtest_metrics, managed, report_paths)


def _prepare_orders_for_backtest(
    bars: List[Dict[str, object]],
    rules: List[RuleConfig],
) -> Dict[datetime, List[Order]]:
    df = pd.DataFrame(bars)
    df["dt"] = pd.to_datetime(df["dt"])
    orders_by_date: Dict[datetime, List[Order]] = {}
    engine = StrategyEngine(rules)

    for symbol, group in df.groupby("symbol"):
        group = group.set_index("dt").sort_index()
        evaluated = engine.evaluate(group)
        evaluated["symbol"] = symbol
        orders = generate_orders_from_signals(evaluated, symbol=symbol)
        for order in orders:
            orders_by_date.setdefault(order.created_at, []).append(order)
    return orders_by_date


def _pass_criteria(metrics: Dict[str, float], criteria: BacktestCriteria) -> bool:
    total_return = metrics.get("total_return", 0.0)
    max_drawdown = abs(metrics.get("max_drawdown", 0.0))
    if total_return < criteria.min_total_return:
        return False
    if max_drawdown > criteria.max_drawdown:
        return False
    return True


def _generate_reports(
    config: TradingCycleConfig,
    trading_result: Dict[str, object],
    managed: ManagedTradingResult,
    backtest_metrics: Dict[str, float],
) -> Optional[Dict[str, Path]]:
    payload_raw = load_report_payload(config.strategy_id, config.session_id)
    if not payload_raw.get("equity") and not payload_raw.get("trades"):
        return None
    metadata: Dict[str, object] = {
        "strategy_id": config.strategy_id,
        "session_id": config.session_id,
        "execution_mode": config.execution_mode,
        "status": "executed" if managed.decision.proceed else "risk_blocked",
        "alerts": managed.decision.alerts,
        "backtest_metrics": backtest_metrics,
    }
    payload = ReportPayload(
        generated_at=datetime.utcnow(),
        metadata=metadata,
        equity_curve=payload_raw.get("equity", []),
        trades=payload_raw.get("trades", []),
        orders=payload_raw.get("orders", []),
        llm_logs=payload_raw.get("logs", []),
    )
    builder = ReportBuilder()
    report_result = builder.build(payload)
    writer = ReportWriter(get_settings().trading.report_output_dir)
    return writer.write(report_result)


__all__ = [
    "BacktestCriteria",
    "AutoTradingConfig",
    "AutoTradingResult",
    "run_full_automation",
]


def _main() -> None:  # pragma: no cover - 简易 CLI
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run full auto trading pipeline")
    parser.add_argument("--session", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--symbols", nargs="+", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--backtest-start", required=True)
    parser.add_argument("--backtest-end", required=True)
    parser.add_argument("--min-return", type=float, default=0.0)
    parser.add_argument("--max-drawdown", type=float, default=0.2)
    parser.add_argument(
        "--execution-mode",
        choices=["sandbox", "live"],
        default=None,
        help="交易执行模式（默认使用 TRADING_EXECUTION_MODE）",
    )
    args = parser.parse_args()

    trading_cfg = TradingCycleConfig(
        session_id=args.session,
        strategy_id=args.strategy,
        symbols=args.symbols,
        objective=args.objective,
        history_start=datetime.fromisoformat(args.backtest_start),
        llm_base_url=get_settings().trading.llm_base_url or None,
        symbol_universe_limit=get_settings().trading.symbol_universe_limit,
        execution_mode=args.execution_mode or get_settings().trading.execution_mode,
    )
    auto_cfg = AutoTradingConfig(
        trading=trading_cfg,
        backtest_start=datetime.fromisoformat(args.backtest_start),
        backtest_end=datetime.fromisoformat(args.backtest_end),
        criteria=BacktestCriteria(min_total_return=args.min_return, max_drawdown=args.max_drawdown),
    )
    result = run_full_automation(auto_cfg)
    payload = {
        "status": result.status,
        "backtest": result.backtest_metrics,
        "risk_alerts": [] if result.managed_result is None else result.managed_result.decision.alerts,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    _main()
