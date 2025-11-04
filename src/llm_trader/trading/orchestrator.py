"""AI 驱动的自动交易编排模块。

核心职责：
1. 拉取实时行情快照；
2. 调用大模型生成交易策略规则；
3. 基于历史行情生成交易信号并形成订单；
4. 将订单交给 `TradingSession` 执行并记录流水。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

import pandas as pd

from llm_trader.api.utils import load_ohlcv
from llm_trader.backtest.models import Order, OrderSide
from llm_trader.strategy import (
    LLMStrategyLogRepository,
    PromptTemplateManager,
    generate_orders_from_signals,
)
from llm_trader.strategy.engine import StrategyEngine
from llm_trader.strategy.llm_generator import (
    LLMStrategyContext,
    LLMStrategyGenerator,
    LLMStrategySuggestion,
)
from llm_trader.trading.execution_adapters import create_execution_adapter
from llm_trader.trading.session import TradingSession, TradingSessionConfig
from llm_trader.data.pipelines.realtime_quotes import RealtimeQuotesPipeline
from llm_trader.data.pipelines.symbols import SymbolsPipeline
from llm_trader.data.repositories.parquet import ParquetRepository
from llm_trader.common import DataSourceError


@dataclass
class TradingCycleConfig:
    """AI 交易循环配置。"""

    session_id: str
    strategy_id: str
    symbols: Sequence[str]  # 候选标的列表，模型可从中挑选最终交易标的
    objective: str
    indicators: Sequence[str] = field(default_factory=lambda: ("sma", "ema", "rsi"))
    freq: str = "D"
    history_start: Optional[datetime] = None
    history_end: Optional[datetime] = None
    initial_cash: float = 1_000_000.0
    llm_model: str = "gpt-4.1-mini"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    only_latest_bar: bool = True  # 只对最近一个 bar 生成订单，避免重复建仓
    symbol_universe_limit: Optional[int] = None
    execution_mode: str = "sandbox"
    selection_metric: str = "amount"


def run_ai_trading_cycle(
    config: TradingCycleConfig,
    *,
    generator: Optional[LLMStrategyGenerator] = None,
    trading_session: Optional[TradingSession] = None,
    realtime_pipeline: Optional[RealtimeQuotesPipeline] = None,
    log_repository: Optional[LLMStrategyLogRepository] = None,
    load_ohlcv_fn=load_ohlcv,
) -> Dict[str, object]:
    """执行一次完整的 AI 交易循环并返回执行详情。"""

    use_manual_symbols = bool(config.symbols)
    pipeline = realtime_pipeline or RealtimeQuotesPipeline(
        symbols_limit=config.symbol_universe_limit if use_manual_symbols else None
    )
    universe_symbols = config.symbols if use_manual_symbols else None

    quotes_universe = pipeline.sync(universe_symbols)
    if not quotes_universe:
        raise ValueError("未获取到实时行情数据")

    candidate_symbols = resolve_candidate_symbols(config, quotes_universe)
    if not candidate_symbols:
        raise ValueError("选股逻辑未返回任何标的")

    selected_set = set(candidate_symbols)
    quotes = [item for item in quotes_universe if item.get("symbol") in selected_set]
    if len(quotes) < len(candidate_symbols):
        quotes = pipeline.sync(candidate_symbols)
    summary = _summarize_quotes(quotes)

    if generator is None:
        template_manager = PromptTemplateManager()
        llm = LLMStrategyGenerator(
            model=config.llm_model,
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            template_manager=template_manager,
        )
    else:
        llm = generator
    context = LLMStrategyContext(
        objective=config.objective,
        symbols=candidate_symbols,
        indicators=config.indicators,
        historical_summary=summary,
    )
    suggestion = llm.generate(context)
    chosen_symbols = suggestion.selected_symbols or candidate_symbols
    pipeline_symbols = list(dict.fromkeys(chosen_symbols))

    if log_repository is None:
        log_repository = LLMStrategyLogRepository()
    last_prompt = getattr(llm, "last_prompt", None)
    last_raw = getattr(llm, "last_raw_response", None)
    if last_prompt and last_raw:
        log_repository.append(
            strategy_id=config.strategy_id,
            session_id=config.session_id,
            prompt=last_prompt,
            response=last_raw,
            payload={
                "suggestion_description": suggestion.description,
                "rules": [
                    {
                        "indicator": rule.indicator,
                        "column": rule.column,
                        "params": rule.params,
                        "operator": rule.operator,
                        "threshold": rule.threshold,
                    }
                    for rule in suggestion.rules
                ],
                "objective": config.objective,
                "symbols": list(config.symbols),
                "indicators": list(config.indicators),
                "quotes_summary": summary,
                "selected_symbols": pipeline_symbols,
            },
        )

    if pipeline_symbols != candidate_symbols:
        quotes = pipeline.sync(pipeline_symbols)

    adapter = create_execution_adapter(getattr(config, "execution_mode", "sandbox"))
    session = trading_session or TradingSession(
        TradingSessionConfig(
            session_id=config.session_id,
            strategy_id=config.strategy_id,
            initial_cash=config.initial_cash,
        ),
        adapter=adapter,
    )

    bars = load_ohlcv_fn(pipeline_symbols, config.freq, config.history_start, config.history_end)
    if not bars:
        raise ValueError("缺少历史行情数据，无法评估策略")

    derived_config = TradingCycleConfig(
        session_id=config.session_id,
        strategy_id=config.strategy_id,
        symbols=pipeline_symbols,
        objective=config.objective,
        indicators=config.indicators,
        freq=config.freq,
        history_start=config.history_start,
        history_end=config.history_end,
        initial_cash=config.initial_cash,
        llm_model=config.llm_model,
        llm_api_key=config.llm_api_key,
        llm_base_url=config.llm_base_url,
        only_latest_bar=config.only_latest_bar,
        execution_mode=config.execution_mode,
    )

    orders_by_dt = _generate_orders(bars, suggestion, derived_config)
    price_lookup = _build_price_lookup(quotes, bars)

    executed_trades: List[Order] = []
    if not orders_by_dt:
        session.execute(datetime.utcnow(), [], price_lookup)
    else:
        for dt in sorted(orders_by_dt.keys()):
            trades = session.execute(dt, orders_by_dt[dt], price_lookup)
            executed_trades.extend(trades)

    return {
        "suggestion": suggestion,
        "llm_prompt": last_prompt,
        "llm_response": last_raw,
        "quotes": quotes,
        "orders_executed": sum(len(v) for v in orders_by_dt.values()),
        "trades_filled": len(executed_trades),
        "session": session,
        "selected_symbols": pipeline_symbols,
        "config": derived_config,
    }


def _summarize_quotes(quotes: Iterable[Dict[str, object]]) -> str:
    """构建简单的行情摘要，供提示词使用。"""

    lines: List[str] = []
    for item in quotes:
        symbol = item.get("symbol", "")
        last_price = item.get("last_price")
        change_ratio = item.get("change_ratio")
        turnover = item.get("turnover_rate")
        parts = [f"{symbol} 最新价 {last_price}"]
        if change_ratio is not None:
            parts.append(f"涨跌幅 {change_ratio}")
        if turnover is not None:
            parts.append(f"换手率 {turnover}")
        lines.append(", ".join(parts))
    return "；".join(lines)


def _generate_orders(
    bars: Sequence[Dict[str, object]],
    suggestion: LLMStrategySuggestion,
    config: TradingCycleConfig,
) -> Dict[datetime, List[Order]]:
    df = pd.DataFrame(bars)
    df["dt"] = pd.to_datetime(df["dt"])

    engine = StrategyEngine(suggestion.rules)
    orders_by_dt: Dict[datetime, List[Order]] = defaultdict(list)

    for symbol, group in df.groupby("symbol"):
        group = group.set_index("dt").sort_index()
        evaluated = engine.evaluate(group)
        evaluated["symbol"] = symbol
        orders = generate_orders_from_signals(evaluated, symbol=symbol)

        if config.only_latest_bar and not group.empty:
            latest_dt = group.index.max()
            orders = [order for order in orders if order.created_at == latest_dt]

        for order in orders:
            orders_by_dt[order.created_at].append(order)

    return orders_by_dt


def _build_price_lookup(
    quotes: Iterable[Dict[str, object]],
    bars: Sequence[Dict[str, object]],
) -> callable:
    latest_price: Dict[str, float] = {}
    for quote in quotes:
        symbol = quote.get("symbol")
        price = quote.get("last_price")
        if symbol and price:
            latest_price[symbol] = float(price)

    fallback_price: Dict[str, float] = {}
    for record in bars:
        symbol = record.get("symbol")
        close = record.get("close")
        if symbol and close:
            fallback_price[symbol] = float(close)

    def price_lookup(symbol: str, _side: OrderSide) -> float:
        if symbol in latest_price:
            return latest_price[symbol]
        return fallback_price.get(symbol, 0.0)

    return price_lookup


__all__ = ["TradingCycleConfig", "run_ai_trading_cycle", "resolve_candidate_symbols"]


def _select_symbols_from_quotes(
    quotes: List[Dict[str, object]],
    *,
    metric: str,
    limit: Optional[int],
) -> List[str]:
    if not quotes:
        return []
    df = pd.DataFrame(quotes)
    if df.empty or "symbol" not in df.columns:
        return []
    metric_column = metric if metric in df.columns else "amount" if "amount" in df.columns else None
    if metric_column is None:
        return list(dict.fromkeys(df["symbol"].tolist()[: (limit or len(df))]))
    values = pd.to_numeric(df[metric_column], errors="coerce").fillna(0.0)
    df = df.assign(_metric=values)
    df = df.sort_values("_metric", ascending=False)
    symbols = df["symbol"].dropna().astype(str).tolist()
    if limit is not None:
        symbols = symbols[:limit]
    # 去重保持顺序
    seen = set()
    ordered = []
    for symbol in symbols:
        if symbol not in seen:
            ordered.append(symbol)
            seen.add(symbol)
    return ordered


def resolve_candidate_symbols(
    config: TradingCycleConfig,
    quotes: Optional[List[Dict[str, object]]] = None,
) -> List[str]:
    candidate_symbols = [symbol for symbol in config.symbols if str(symbol).strip()]
    limit = config.symbol_universe_limit
    if candidate_symbols:
        if limit is not None:
            candidate_symbols = candidate_symbols[:limit]
        return list(dict.fromkeys(candidate_symbols))

    if quotes:
        selected = _select_symbols_from_quotes(quotes, metric=config.selection_metric, limit=limit)
        if selected:
            return selected

    repository = ParquetRepository()
    symbols = repository.list_active_symbols(limit=limit)
    if not symbols:
        SymbolsPipeline(repository=repository).sync()
        symbols = repository.list_active_symbols(limit=limit)
    if not symbols:
        raise DataSourceError("未找到可用标的，请先同步证券主表")
    return symbols
