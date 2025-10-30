"""API 配置管理。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class APIConfig:
    api_key: str
    rate_limit_per_minute: int


def get_api_config() -> APIConfig:
    api_key = os.getenv("LLM_TRADER_API_KEY", "")
    rate_limit_raw = os.getenv("LLM_TRADER_RATE_LIMIT", "60")
    try:
        rate_limit = int(rate_limit_raw)
    except ValueError:
        rate_limit = 60
    return APIConfig(api_key=api_key, rate_limit_per_minute=max(rate_limit, 1))
