"""验证数据存储路径生成逻辑。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from llm_trader.data import DataStoreManager, DatasetConfig, DatasetKind, default_manager


def test_default_manager_symbols_path(tmp_path: Path) -> None:
    """默认管理器应能生成证券主表路径。"""

    manager = default_manager(base_dir=tmp_path)
    path = manager.path_for(DatasetKind.SYMBOLS)
    assert path == tmp_path / "metadata" / "symbols.parquet"
    assert path.parent.exists()


def test_daily_ohlcv_partition_path(tmp_path: Path) -> None:
    """日线分区路径应按模板展开。"""

    manager = default_manager(base_dir=tmp_path)
    dt = datetime(2024, 7, 1)
    path = manager.path_for(
        DatasetKind.OHLCV_DAILY,
        symbol="600000.SH",
        freq="D",
        timestamp=dt,
    )
    expected = tmp_path / "ohlcv" / "daily" / "freq=D" / "symbol=600000.SH" / "year=2024" / "month=07" / "20240701.parquet"
    assert path == expected
    assert path.parent.exists()


def test_register_custom_dataset(tmp_path: Path) -> None:
    """自定义数据集注册后应能生成路径。"""

    manager = DataStoreManager(base_dir=tmp_path)
    config = DatasetConfig(
        kind="custom_dataset",
        relative_dir="custom/data",
        filename_template="{symbol}.parquet",
        partition_template="symbol={symbol}",
        description="自定义数据集",
    )
    manager.register(config)
    path = manager.path_for("custom_dataset", symbol="TEST")
    assert path == tmp_path / "custom" / "data" / "symbol=TEST" / "TEST.parquet"


def test_directory_for_creates_folder(tmp_path: Path) -> None:
    """directory_for 应确保目录存在。"""

    manager = default_manager(base_dir=tmp_path)
    directory = manager.directory_for(DatasetKind.FUNDAMENTALS)
    assert directory == tmp_path / "fundamentals"
    assert directory.exists()
