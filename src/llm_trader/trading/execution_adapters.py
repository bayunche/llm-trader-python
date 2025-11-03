"""交易执行模式适配器。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, List, Sequence

from llm_trader.backtest.models import Order, Trade
from llm_trader.common import get_logger
from llm_trader.config import get_settings
from llm_trader.trading.brokers.base import BrokerClient, BrokerConfig
from llm_trader.trading.brokers.mock import MockBrokerClient

_LOGGER = get_logger("trading.execution")

if TYPE_CHECKING:  # pragma: no cover - 类型检查分支
    from .session import PriceLookup, TradingSession


class ExecutionAdapter(ABC):
    """交易执行适配器抽象基类。"""

    @abstractmethod
    def execute(
        self,
        session: "TradingSession",
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: "PriceLookup",
    ) -> List[Trade]:
        """执行订单并返回成交结果。"""


class SandboxExecutionAdapter(ExecutionAdapter):
    """沙盒执行，复用本地撮合引擎。"""

    def execute(
        self,
        session: "TradingSession",
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: "PriceLookup",
    ) -> List[Trade]:
        return session._execute_sandbox(dt, orders, price_lookup)  # noqa: SLF001


class LiveBrokerExecutionAdapter(ExecutionAdapter):
    """实盘执行适配器，委托给券商客户端。"""

    def __init__(self, config: BrokerConfig) -> None:
        self._config = config
        self._logger = get_logger("trading.execution.live")

    def _build_broker_client(self, price_lookup: "PriceLookup") -> BrokerClient:
        provider = (self._config.provider or "mock").lower()
        if provider == "mock":
            return MockBrokerClient(self._config, price_lookup)
        raise NotImplementedError(f"暂不支持的券商提供方：{provider}")

    def execute(
        self,
        session: "TradingSession",
        dt: datetime,
        orders: Sequence[Order],
        price_lookup: "PriceLookup",
    ) -> List[Trade]:
        client = self._build_broker_client(price_lookup)
        trades = session._execute_live(dt, orders, price_lookup, client)
        self._logger.info(
            "live 执行完成",
            extra={
                "broker": self._config.provider,
                "session_id": session.config.session_id,
                "strategy_id": session.config.strategy_id,
                "orders": len(orders),
                "trades": len(trades),
            },
        )
        return trades


def create_execution_adapter(mode: str) -> ExecutionAdapter:
    """根据执行模式创建适配器实例。"""

    normalized = (mode or "sandbox").strip().lower()
    if normalized == "live":
        settings = get_settings().trading
        config = BrokerConfig(
            provider=settings.broker_provider,
            account=settings.broker_account,
            base_url=settings.broker_base_url,
            api_key=settings.broker_api_key,
        )
        if config.provider.lower() == "mock":
            _LOGGER.warning(
                "live 模式使用 mock 券商，仅用于模拟真实交易流程",
                extra={"requested_mode": normalized},
            )
        return LiveBrokerExecutionAdapter(config)
    return SandboxExecutionAdapter()


__all__ = [
    "ExecutionAdapter",
    "SandboxExecutionAdapter",
    "LiveBrokerExecutionAdapter",
    "create_execution_adapter",
]
