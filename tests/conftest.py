"""测试层公共夹具定义。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest

# 将 src 目录加入 sys.path，确保测试可直接导入包
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_PATH = _PROJECT_ROOT / ".codex" / "vendor"
_SRC_PATH = _PROJECT_ROOT / "src"

if _VENDOR_PATH.exists() and str(_VENDOR_PATH) not in sys.path:
    sys.path.append(str(_VENDOR_PATH))
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from fastapi.testclient import TestClient

from llm_trader.api.app import app
from llm_trader.api.security import reset_rate_limits
from llm_trader.config import AppSettings, get_settings
from llm_trader.common.paths import data_store_dir


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    """提供全局配置实例，避免重复加载。"""

    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def ensure_data_directory(app_settings: AppSettings) -> Iterator[Path]:
    """在测试前保证数据目录存在。"""

    path = data_store_dir()
    yield path


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    """为 API 测试提供独立的客户端实例，并在前后重置限流状态。"""

    reset_rate_limits()
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        reset_rate_limits()
