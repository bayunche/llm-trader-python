from __future__ import annotations

"""
Alembic 迁移环境配置，加载 llm_trader 的 SQLModel 元数据。
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from llm_trader.db import metadata  # noqa: F401
from llm_trader.db.models import (  # noqa: F401
    AccountSnapshot,
    CheckerResult,
    Decision,
    DecisionAction,
    DecisionLedger,
    Fill,
    LLMCallAudit,
    MasterSymbol,
    ModelEndpoint,
    Observation,
    Order,
    PerformanceSnapshot,
    PromptTemplate,
    RiskConfiguration,
    RiskResult,
    SystemState,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def get_database_url() -> str:
    """
    优先使用环境变量 DATABASE_URL，未提供时回落到配置文件。
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """
    离线模式下生成迁移脚本。
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式直接执行迁移。
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
