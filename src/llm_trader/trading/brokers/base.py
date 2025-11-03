"""实盘券商客户端接口定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from llm_trader.backtest.models import Order, OrderSide, Trade


@dataclass
class BrokerConfig:
    """券商连接配置。"""

    provider: str
    account: str
    base_url: str = ""
    api_key: str = ""


class BrokerClient(ABC):
    """券商客户端抽象基类。"""

    def __init__(self, config: BrokerConfig) -> None:
        self.config = config

    @abstractmethod
    def submit_orders(self, orders: Iterable[Order], dt: datetime) -> List[Trade]:
        """提交订单并返回成交。"""

    @abstractmethod
    def sync_positions(self) -> None:
        """同步账户持仓（如需）。"""


__all__ = ["BrokerClient", "BrokerConfig"]
