from __future__ import annotations

"""
数据库会话管理，基于配置构建 SQLModel Session。
"""

from contextlib import contextmanager
from typing import Callable, ContextManager, Optional

from sqlmodel import Session

from .base import get_engine


@contextmanager
def session_scope(*, echo: Optional[bool] = None) -> ContextManager[Session]:
    """
    提供数据库会话上下文，自动提交或回滚。
    """

    from llm_trader.config import get_settings

    settings = get_settings().database
    engine = get_engine(
        database_url=settings.url,
        echo=echo if echo is not None else settings.echo,
    )
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_session_factory(*, echo: Optional[bool] = None) -> Callable[[], ContextManager[Session]]:
    """
    返回可重复使用的 Session 工厂，便于注入到服务中。
    """

    def factory() -> ContextManager[Session]:
        return session_scope(echo=echo)

    return factory


__all__ = ["session_scope", "create_session_factory"]
