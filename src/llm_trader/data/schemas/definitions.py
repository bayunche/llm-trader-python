"""数据实体字段定义。

该模块描述数据层核心实体的字段结构，便于在采集、存储与验证过程中复用。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class FieldSpec:
    """字段说明，包括名称、数据类型与描述。"""

    name: str
    dtype: str
    description: str


@dataclass(frozen=True)
class EntitySchema:
    """实体级 schema，包含字段列表与主键说明。"""

    name: str
    description: str
    primary_keys: List[str]
    fields: List[FieldSpec]


SYMBOLS_SCHEMA = EntitySchema(
    name="symbols",
    description="证券主表，存储基础元数据。",
    primary_keys=["symbol"],
    fields=[
        FieldSpec("symbol", "string", "证券代码（含交易所后缀，如 600000.SH）"),
        FieldSpec("name", "string", "证券简称"),
        FieldSpec("board", "string", "板块类别（主板/科创/创业等）"),
        FieldSpec("listed_date", "date", "上市日期"),
        FieldSpec("delisted_date", "date?", "退市日期，未退市时为空"),
        FieldSpec("status", "string", "状态标识：active/suspended/delisted"),
        FieldSpec("exchange", "string", "交易所代码"),
        FieldSpec("industry", "string", "所属行业，可为空"),
    ],
)

TRADING_CALENDAR_SCHEMA = EntitySchema(
    name="trading_calendar",
    description="交易日历，记录每日开休市信息。",
    primary_keys=["date", "market"],
    fields=[
        FieldSpec("date", "date", "交易日期"),
        FieldSpec("market", "string", "市场标识，如 CN_A"),
        FieldSpec("is_trading_day", "bool", "是否为交易日"),
    ],
)

OHLCV_SCHEMA = EntitySchema(
    name="ohlcv",
    description="K线行情数据，支持日线与分钟线。",
    primary_keys=["symbol", "dt", "freq"],
    fields=[
        FieldSpec("symbol", "string", "证券代码"),
        FieldSpec("dt", "datetime", "时间戳（按频率对齐）"),
        FieldSpec("freq", "string", "频率标识，如 D/5m/1m"),
        FieldSpec("open", "float", "开盘价"),
        FieldSpec("high", "float", "最高价"),
        FieldSpec("low", "float", "最低价"),
        FieldSpec("close", "float", "收盘价"),
        FieldSpec("volume", "float", "成交量"),
        FieldSpec("amount", "float", "成交额"),
        FieldSpec("turnover_rate", "float?", "换手率，可选"),
        FieldSpec("adj_factor", "float?", "复权因子，可选"),
        FieldSpec("suspended", "bool", "是否停牌"),
    ],
)

FUNDAMENTALS_SCHEMA = EntitySchema(
    name="fundamentals",
    description="基础指标与财务摘要，字段可按配置扩展。",
    primary_keys=["symbol", "date"],
    fields=[
        FieldSpec("symbol", "string", "证券代码"),
        FieldSpec("date", "date", "数据对应日期"),
        FieldSpec("pe", "float?", "市盈率"),
        FieldSpec("pb", "float?", "市净率"),
        FieldSpec("mkt_cap", "float?", "总市值"),
        FieldSpec("float_mkt_cap", "float?", "流通市值"),
        FieldSpec("turnover", "float?", "换手率"),
        FieldSpec("industry", "string?", "行业分类"),
    ],
)


__all__ = [
    "FieldSpec",
    "EntitySchema",
    "SYMBOLS_SCHEMA",
    "TRADING_CALENDAR_SCHEMA",
    "OHLCV_SCHEMA",
    "FUNDAMENTALS_SCHEMA",
]
