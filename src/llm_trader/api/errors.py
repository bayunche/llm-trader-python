"""API 错误码与异常定义。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    DATA_SOURCE_LIMITED = "E-DS-429"
    DATA_NOT_FOUND = "E-DS-404"
    BACKTEST_FAILURE = "E-BT-500"
    STRATEGY_INVALID = "E-ST-400"
    INTERNAL_ERROR = "E-GEN-500"


class APIException(HTTPException):
    def __init__(
        self,
        *,
        error_code: ErrorCode,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        self.error_code = error_code
        self.extra = extra or {}
        super().__init__(status_code=status_code, detail={"error_code": error_code, "message": detail, **self.extra})
