"""验证基础设施是否正确初始化。"""

from __future__ import annotations

from pathlib import Path

from llm_trader.common import get_logger, project_root
from llm_trader.common.paths import data_store_dir


def test_project_root_exists() -> None:
    """项目根目录应当存在。"""

    assert project_root().exists()


def test_data_store_directory_created() -> None:
    """数据目录初始化后必须存在。"""

    path = data_store_dir()
    assert path.exists()
    assert path.is_dir()


def test_logging_setup() -> None:
    """日志记录器应当可直接使用。"""

    logger = get_logger("tests.bootstrap")
    logger.info("日志初始化验证")
    assert logger.name == "tests.bootstrap"
