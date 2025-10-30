"""路径与目录相关的工具函数。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from llm_trader.config import get_settings

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """返回项目根目录。"""

    return _PROJECT_ROOT


def data_store_dir(*extra: str, ensure_exists: bool = True) -> Path:
    """获取数据存储目录，可附加子路径。

    参数:
        *extra: 追加的子目录名称
        ensure_exists: 是否自动创建目录
    """

    base = get_settings().data_store.resolve_base_dir()
    target = base.joinpath(*extra) if extra else base
    if ensure_exists:
        target.mkdir(parents=True, exist_ok=True)
    return target


def resolve_path(relative: str) -> Path:
    """将相对路径转换为项目根目录下的绝对路径。"""

    return project_root().joinpath(relative).resolve()


__all__ = ["project_root", "data_store_dir", "resolve_path"]
