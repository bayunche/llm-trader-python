"""数据存储与路径管理模块。

核心职责：
1. 定义各数据集的目录与文件命名规范；
2. 提供统一的路径生成函数，避免魔法字符串；
3. 支持基于配置的分区模板，便于后续扩展。

注：所有注释均使用中文，遵循项目编码规范。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Mapping, Optional

from llm_trader.common import data_store_dir


class DatasetKind(str, Enum):
    """数据集类型枚举，用于标识不同业务领域的数据。"""

    SYMBOLS = "symbols"
    TRADING_CALENDAR = "trading_calendar"
    OHLCV_DAILY = "ohlcv_daily"
    OHLCV_INTRADAY = "ohlcv_intraday"
    FUNDAMENTALS = "fundamentals"
    STRATEGY_SIGNALS = "strategy_signals"
    BACKTEST_RESULTS = "backtest_results"
    REALTIME_QUOTES = "realtime_quotes"
    TRADING_ORDERS = "trading_orders"
    TRADING_TRADES = "trading_trades"
    TRADING_EQUITY = "trading_equity"
    STRATEGY_LLM_LOGS = "strategy_llm_logs"
    STRATEGY_PROMPTS = "strategy_prompts"


@dataclass(frozen=True)
class DatasetConfig:
    """单个数据集的存储配置。"""

    kind: str | DatasetKind
    relative_dir: str
    filename_template: str
    partition_template: Optional[str] = None
    description: str = ""

    def build_context(
        self,
        symbol: Optional[str],
        freq: Optional[str],
        timestamp: Optional[datetime],
    ) -> Dict[str, str]:
        """构建路径模板所需的上下文字典。"""

        context: Dict[str, str] = {}
        if symbol:
            context["symbol"] = symbol
        if freq:
            context["freq"] = freq
        if timestamp:
            context["date"] = timestamp.strftime("%Y%m%d")
            context["year"] = timestamp.strftime("%Y")
            context["month"] = timestamp.strftime("%m")
            context["day"] = timestamp.strftime("%d")
        return context

    def render_partition(self, context: Mapping[str, str]) -> Path:
        """根据上下文渲染分区路径。"""

        if not self.partition_template:
            return Path()
        try:
            return Path(self.partition_template.format(**context))
        except KeyError as exc:  # pragma: no cover - 仅在配置错误时触发
            missing = exc.args[0]
            raise ValueError(f"缺少分区模板所需变量：{missing}") from exc

    def render_filename(self, context: Mapping[str, str]) -> str:
        """根据上下文渲染文件名。"""

        try:
            return self.filename_template.format(**context)
        except KeyError as exc:  # pragma: no cover - 仅在配置错误时触发
            missing = exc.args[0]
            raise ValueError(f"缺少文件名模板所需变量：{missing}") from exc


class DataStoreManager:
    """数据存储访问器，集中管理目录与文件路径。"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or data_store_dir(ensure_exists=True)
        self._configs: Dict[str, DatasetConfig] = {}

    def register(self, config: DatasetConfig) -> None:
        """注册新的数据集配置。"""

        key = config.kind.value if isinstance(config.kind, DatasetKind) else str(config.kind)
        self._configs[key] = config

    def get(self, kind: DatasetKind | str) -> DatasetConfig:
        """获取配置，不存在时抛出错误。"""

        key = kind.value if isinstance(kind, DatasetKind) else str(kind)
        if key not in self._configs:
            raise KeyError(f"未注册数据集配置：{kind}")
        return self._configs[key]

    def path_for(
        self,
        kind: DatasetKind | str,
        *,
        symbol: Optional[str] = None,
        freq: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        ensure_dir: bool = True,
    ) -> Path:
        """生成指定数据集的文件路径。"""

        config = self.get(kind)
        context = config.build_context(symbol=symbol, freq=freq, timestamp=timestamp)
        partition = config.render_partition(context)
        directory = self.base_dir / config.relative_dir / partition

        if ensure_dir:
            directory.mkdir(parents=True, exist_ok=True)

        filename = config.render_filename(context)
        return directory / filename

    def directory_for(self, kind: DatasetKind | str) -> Path:
        """返回数据集的根目录。"""

        config = self.get(kind)
        directory = self.base_dir / config.relative_dir
        directory.mkdir(parents=True, exist_ok=True)
        return directory


def default_manager(base_dir: Optional[Path] = None) -> DataStoreManager:
    """返回带默认配置的存储管理器。"""

    manager = DataStoreManager(base_dir=base_dir)
    manager.register(
        DatasetConfig(
            kind=DatasetKind.SYMBOLS,
            relative_dir="metadata",
            filename_template="symbols.parquet",
            description="证券主表元数据",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.TRADING_CALENDAR,
            relative_dir="metadata",
            filename_template="trading_calendar.parquet",
            description="交易日历数据",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.OHLCV_DAILY,
            relative_dir="ohlcv/daily",
            partition_template="freq={freq}/symbol={symbol}/year={year}/month={month}",
            filename_template="{date}.parquet",
            description="日线行情数据",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.OHLCV_INTRADAY,
            relative_dir="ohlcv/intraday",
            partition_template="freq={freq}/symbol={symbol}/date={date}",
            filename_template="{symbol}_{freq}.parquet",
            description="分钟线行情数据",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.FUNDAMENTALS,
            relative_dir="fundamentals",
            partition_template="symbol={symbol}/year={year}",
            filename_template="{symbol}_{year}.parquet",
            description="基础指标与财务摘要",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.STRATEGY_SIGNALS,
            relative_dir="strategies/signals",
            partition_template="strategy={symbol}/version={freq}",
            filename_template="signals.parquet",
            description="策略信号输出（symbol=策略ID，freq=版本号）",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.BACKTEST_RESULTS,
            relative_dir="backtests",
            partition_template="strategy={symbol}/run_date={date}",
            filename_template="result.parquet",
            description="回测结果集（symbol=策略ID）",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.REALTIME_QUOTES,
            relative_dir="realtime/quotes",
            partition_template="date={date}",
            filename_template="quotes_{symbol}_{year}{month}{day}.parquet",
            description="实时行情快照",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.TRADING_ORDERS,
            relative_dir="trading/orders",
            partition_template="session={symbol}/strategy={freq}/date={date}",
            filename_template="orders.parquet",
            description="自动交易订单流水",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.TRADING_TRADES,
            relative_dir="trading/trades",
            partition_template="session={symbol}/strategy={freq}/date={date}",
            filename_template="trades.parquet",
            description="自动交易成交流水",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.TRADING_EQUITY,
            relative_dir="trading/equity",
            partition_template="session={symbol}/strategy={freq}",
            filename_template="equity.parquet",
            description="自动交易权益曲线与资金快照",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.STRATEGY_LLM_LOGS,
            relative_dir="strategies/llm_logs",
            partition_template="strategy={symbol}/session={freq}/date={date}",
            filename_template="logs.jsonl",
            description="LLM 策略提示与响应记录",
        )
    )
    manager.register(
        DatasetConfig(
            kind=DatasetKind.STRATEGY_PROMPTS,
            relative_dir="prompts/templates",
            filename_template="{symbol}.txt",
            description="可编辑提示词模板（symbol=模板名称）",
        )
    )
    return manager


__all__ = ["DatasetKind", "DatasetConfig", "DataStoreManager", "default_manager"]
