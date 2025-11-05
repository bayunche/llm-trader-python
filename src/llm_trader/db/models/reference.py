from __future__ import annotations

"""
参考数据与统计快照实体。
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String
from sqlmodel import Field, SQLModel

from llm_trader.db.models.enums import RiskPosture


class MasterSymbol(SQLModel, table=True):
    """主表证券基础信息。"""

    __tablename__ = "master_symbols"

    symbol: str = Field(
        sa_column=Column(String(32), primary_key=True),
        description="证券代码（含交易所后缀）",
    )
    exchange: str = Field(
        sa_column=Column(String(8), nullable=False, index=True),
        description="交易所",
    )
    board: str = Field(
        sa_column=Column(String(32), nullable=False),
        description="板块分类",
    )
    name: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="证券简称",
    )
    is_st: bool = Field(
        sa_column=Column(Boolean, nullable=False),
        description="是否 ST",
    )
    list_date: date = Field(
        sa_column=Column(Date, nullable=False),
        description="上市日期",
    )
    industry: str = Field(
        sa_column=Column(String(64), nullable=False),
        description="行业分类",
    )
    market_cap: float = Field(
        sa_column=Column(Float, nullable=False),
        description="总市值",
    )
    float_cap: float = Field(
        sa_column=Column(Float, nullable=False),
        description="流通市值",
    )
    pe_ttm: float = Field(
        sa_column=Column(Float, nullable=True),
        description="滚动市盈率",
    )
    pb: float = Field(
        sa_column=Column(Float, nullable=True),
        description="市净率",
    )
    tick_size: float = Field(
        sa_column=Column(Float, nullable=False),
        description="最小变动价位",
    )
    lot_size: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="最小交易单位",
    )
    trading_status: str = Field(
        sa_column=Column(String(16), nullable=False, index=True),
        description="交易状态",
    )
    as_of_date: date = Field(
        sa_column=Column(Date, nullable=False, index=True),
        description="数据快照日期",
    )
    version: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="版本号",
    )


class AccountSnapshot(SQLModel, table=True):
    """账户资金快照。"""

    __tablename__ = "account_snapshots"

    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=True),
        description="自增主键",
    )
    captured_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        description="快照时间",
    )
    nav: float = Field(
        sa_column=Column(Float, nullable=False),
        description="净值",
    )
    cash: float = Field(
        sa_column=Column(Float, nullable=False),
        description="现金",
    )
    available: float = Field(
        sa_column=Column(Float, nullable=False),
        description="可用资金",
    )
    risk_posture: RiskPosture = Field(
        sa_column=Column(String(32), nullable=False, default=RiskPosture.NORMAL.value),
        description="风险姿态",
    )


class PerformanceSnapshot(SQLModel, table=True):
    """日度绩效指标。"""

    __tablename__ = "performance_snapshots"

    trade_date: date = Field(
        sa_column=Column(Date, primary_key=True),
        description="交易日",
    )
    nav: float = Field(
        sa_column=Column(Float, nullable=False),
        description="期末净值",
    )
    pnl: float = Field(
        sa_column=Column(Float, nullable=False),
        description="当日盈亏",
    )
    max_drawdown: float = Field(
        sa_column=Column(Float, nullable=False),
        description="最大回撤",
    )
    win_rate: float = Field(
        sa_column=Column(Float, nullable=False),
        description="胜率",
    )
    order_count: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="委托数量",
    )
    cancel_count: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="撤单数量",
    )
    fill_count: int = Field(
        sa_column=Column(Integer, nullable=False),
        description="成交数量",
    )
