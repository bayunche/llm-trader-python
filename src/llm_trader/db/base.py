from __future__ import annotations

"""
数据库基础设施：统一的 SQLModel 元数据、引擎构造与会话管理。
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import MetaData
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
SQLModel.metadata = metadata

_engine: Optional[Engine] = None


def get_database_url() -> str:
    """
    读取数据库连接串，默认使用环境变量 DATABASE_URL。
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("未配置 DATABASE_URL，无法初始化 PostgreSQL 连接。")
    return database_url


def get_engine(database_url: Optional[str] = None, echo: bool = False) -> Engine:
    """
    创建或返回全局 Engine，避免重复建连。
    """
    global _engine
    if _engine is not None:
        return _engine

    url = database_url or get_database_url()
    _engine = create_engine(url, echo=echo, pool_pre_ping=True)
    return _engine


@contextmanager
def get_session(database_url: Optional[str] = None, echo: bool = False) -> Generator[Session, None, None]:
    """
    提供会话上下文，自动处理提交与回滚。
    """
    engine = get_engine(database_url=database_url, echo=echo)
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
