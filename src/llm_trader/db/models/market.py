from __future__ import annotations

"""
行情与账户持仓相关的数据库实体。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint
from sqlmodel import Field, SQLModel


class RealtimeQuote(SQLModel, table=True):
    """实时行情快照表。"""

    __tablename__ = "realtime_quotes"
    __table_args__ = (UniqueConstraint("symbol", name="uq_realtime_quotes_symbol"),)

    symbol: str = Field(
        sa_column=Column(String(32), primary_key=True),
        description="证券代码（含交易所后缀）",
    )
    name: str = Field(
        sa_column=Column(String(64), nullable=True),
        description="证券简称",
    )
    last_price: float = Field(
        sa_column=Column(Float, nullable=True),
        description="最新价格",
    )
    change: float = Field(
        sa_column=Column(Float, nullable=True),
        description="涨跌额",
    )
    change_ratio: float = Field(
        sa_column=Column(Float, nullable=True),
        description="涨跌幅(%)",
    )
    volume: float = Field(
        sa_column=Column(Float, nullable=True),
        description="成交量(股)",
    )
    amount: float = Field(
        sa_column=Column(Float, nullable=True),
        description="成交额(元)",
    )
    high: float = Field(
        sa_column=Column(Float, nullable=True),
        description="当日最高",
    )
    low: float = Field(
        sa_column=Column(Float, nullable=True),
        description="当日最低",
    )
    open: float = Field(
        sa_column=Column(Float, nullable=True),
        description="开盘价",
    )
    prev_close: float = Field(
        sa_column=Column(Float, nullable=True),
        description="昨收",
    )
    turnover_rate: float = Field(
        sa_column=Column(Float, nullable=True),
        description="换手率(%)",
    )
    amplitude: float = Field(
        sa_column=Column(Float, nullable=True),
        description="振幅(%)",
    )
    pe: float = Field(
        sa_column=Column(Float, nullable=True),
        description="市盈率",
    )
    snapshot_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="快照时间",
    )


class AccountPosition(SQLModel, table=True):
    """账户持仓快照。"""

    __tablename__ = "account_positions"
    __table_args__ = (UniqueConstraint("captured_at", "symbol", name="uq_account_positions"),)

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
        description="自增主键",
    )
    captured_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="快照时间",
    )
    symbol: str = Field(
        sa_column=Column(String(32), nullable=False, index=True),
        description="持仓标的",
    )
    qty: float = Field(
        sa_column=Column(Float, nullable=False),
        description="持仓数量",
    )
    avg_price: float = Field(
        sa_column=Column(Float, nullable=True),
        description="持仓成本价",
    )
    market_value: float = Field(
        sa_column=Column(Float, nullable=True),
        description="市值",
    )

