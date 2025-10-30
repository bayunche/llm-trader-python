"""API 安全与限流。"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Depends, Header, HTTPException, status

from .config import APIConfig, get_api_config


# 每个客户端维护近 60 秒内的请求时间戳（monotonic 秒）
_REQUEST_LOG: Dict[str, Deque[float]] = defaultdict(deque)
_WINDOW_SECONDS = 60


def reset_rate_limits() -> None:  # pragma: no cover - 测试辅助
    _REQUEST_LOG.clear()


def _enforce_rate_limit(client_id: str, limit: int) -> None:
    now = time.monotonic()
    q = _REQUEST_LOG[client_id]
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail={"error_code": "E-SEC-429", "message": "请求过于频繁"})
    q.append(now)


def require_api_key(
    api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    config: APIConfig = Depends(get_api_config),
) -> str:
    expected = config.api_key
    if expected:
        if not api_key or api_key != expected:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"error_code": "E-SEC-401", "message": "API Key 无效"})
        _enforce_rate_limit(expected, config.rate_limit_per_minute)
        return expected
    # 未配置 API Key 时仍允许匿名访问，但仍可做基本限流（共享桶）
    anon_id = api_key or "anonymous"
    _enforce_rate_limit(anon_id, config.rate_limit_per_minute)
    return anon_id
