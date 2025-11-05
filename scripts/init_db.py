from __future__ import annotations

"""
数据库初始化脚本，用于执行 Alembic 迁移至最新版本。
"""

import pathlib

from alembic import command
from alembic.config import Config

from llm_trader.db.base import get_database_url


def run_upgrade() -> None:
    """
    执行 upgrade head。
    """
    config_path = pathlib.Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(config_path))
    alembic_cfg.set_main_option("sqlalchemy.url", get_database_url())
    command.upgrade(alembic_cfg, "head")


def main() -> None:
    """
    命令行入口。
    """
    run_upgrade()


if __name__ == "__main__":
    main()
