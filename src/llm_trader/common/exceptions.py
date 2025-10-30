"""统一定义项目中的异常类型。"""

from __future__ import annotations


class LLMTraderError(Exception):
    """项目顶层异常，所有自定义异常均应继承自此类型。"""


class ConfigurationError(LLMTraderError):
    """配置缺失或错误。"""


class DataSourceError(LLMTraderError):
    """外部数据源访问失败或数据异常。"""


class ValidationError(LLMTraderError):
    """数据校验失败。"""


class BacktestError(LLMTraderError):
    """回测流程中的异常。"""


class StrategyError(LLMTraderError):
    """策略生成或执行异常。"""


__all__ = [
    "LLMTraderError",
    "ConfigurationError",
    "DataSourceError",
    "ValidationError",
    "BacktestError",
    "StrategyError",
]
