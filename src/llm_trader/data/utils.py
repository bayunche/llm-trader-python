"""数据层通用工具函数。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pendulum

_EXCHANGE_PREFIX = {
    "SH": "1",
    "SZ": "0",
    "BJ": "0",
}


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """解析东方财富常用的日期字符串。"""

    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        # 东方财富常见格式：YYYYMMDD 或 YYYY-MM-DD
        if "-" in value:
            return pendulum.parse(value).replace(tzinfo=None)
        return pendulum.from_format(value, "YYYYMMDD").replace(tzinfo=None)
    except pendulum.parsing.exceptions.ParserError:
        return None


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """解析日期时间字符串，常用于 K 线时间戳。"""

    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return pendulum.parse(value).replace(tzinfo=None)
    except pendulum.parsing.exceptions.ParserError:
        return None


def build_symbol(code: str, exchange: str) -> str:
    """基于代码与交易所生成标准 symbol。"""

    return f"{code}.{exchange.upper()}"


def to_secid(symbol: str) -> str:
    """将标准 symbol 转换为东方财富使用的 secid。"""

    code, exchange = symbol.split(".")
    prefix = _EXCHANGE_PREFIX.get(exchange.upper())
    if prefix is None:
        raise ValueError(f"不支持的交易所：{exchange}")
    return f"{prefix}.{code}"


__all__ = ["parse_date", "parse_datetime", "build_symbol", "to_secid"]
