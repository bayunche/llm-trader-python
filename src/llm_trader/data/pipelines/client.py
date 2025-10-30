"""东方财富 HTTP 客户端封装。

该模块提供同步版的东方财富数据访问客户端，内置重试与默认请求头，
供数据采集管道复用。所有注释均使用中文，确保后续维护人员理解上下文。"""

from __future__ import annotations

import random
from typing import Any, Dict, Mapping, Optional

import httpx
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from llm_trader.common import DataSourceError, get_logger


_DEFAULT_HEADERS: Mapping[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


class EastMoneyClient:
    """东方财富同步客户端。"""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        headers: Optional[Mapping[str, str]] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._logger = get_logger(self.__class__.__name__)
        merged_headers = dict(_DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(headers=merged_headers, timeout=timeout, transport=transport)

    def close(self) -> None:
        """关闭底层客户端。"""

        self._client.close()

    def __enter__(self) -> "EastMoneyClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    def _retry_policy(self):
        return retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            reraise=True,
        )

    def get_json(self, url: str, params: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """执行 GET 请求并返回 JSON。"""

        policy = self._retry_policy()

        @policy
        def _request() -> Dict[str, Any]:
            # 为了降低被限流概率，随机增加查询参数 t
            effective_params = dict(params or {})
            effective_params.setdefault("t", f"{random.randint(10_000, 99_999)}")
            response = self._client.get(url, params=effective_params)
            response.raise_for_status()
            data = response.json()
            return data

        try:
            payload = _request()
        except RetryError as exc:  # pragma: no cover - 极端情况下触发
            self._logger.error("东方财富接口请求多次失败", exc_info=exc)
            raise DataSourceError("东方财富接口请求失败") from exc

        if not isinstance(payload, dict):
            raise DataSourceError("东方财富接口返回不是 JSON 对象")

        return payload


__all__ = ["EastMoneyClient"]
