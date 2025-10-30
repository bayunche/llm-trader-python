"""统一响应包装工具。"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from .schemas import APIResponse, PaginationMeta

T = TypeVar("T")


def success_response(
    data: Optional[T] = None,
    *,
    message: str = "success",
    meta: Optional[PaginationMeta] = None,
) -> APIResponse[T]:
    return APIResponse[T](code="OK", message=message, data=data, meta=meta)


def error_response(code: str, message: str) -> APIResponse[None]:
    return APIResponse(code=code, message=message, data=None)
