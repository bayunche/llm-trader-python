from __future__ import annotations

"""Redis 客户端工厂。"""

from typing import Optional

from redis import Redis

from llm_trader.config import get_settings
from .logging import get_logger

_LOGGER = get_logger("redis.factory")


def create_redis_client() -> Optional[Redis]:
    """根据配置创建 Redis 客户端，配置禁用或初始化失败时返回 None。"""

    settings = get_settings().redis
    if not settings.enabled:
        return None
    try:
        client = Redis.from_url(settings.url, decode_responses=settings.decode_responses)
        # 进行一次 ping 检测，确保连接可用；失败时捕获异常并返回 None。
        client.ping()
        return client
    except Exception as exc:  # pragma: no cover - 依赖环境的网络错误
        _LOGGER.warning("Redis 初始化失败，已降级为无缓存模式", extra={"error": str(exc)})
        return None


__all__ = ["create_redis_client"]
