"""策略指标库。"""

from __future__ import annotations

from typing import Callable, Dict

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """简单移动平均线。"""

    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """指数移动平均线。"""

    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def momentum(series: pd.Series, window: int) -> pd.Series:
    """动量指标，当前价格与窗口前价格的差值。"""

    return series - series.shift(window)


def rate_of_change(series: pd.Series, window: int) -> pd.Series:
    """变化率指标。"""

    prev = series.shift(window)
    return (series - prev) / prev


def volatility(series: pd.Series, window: int) -> pd.Series:
    """滚动波动率。"""

    return series.pct_change().rolling(window=window, min_periods=window).std()


def volume_ratio(volume: pd.Series, window: int) -> pd.Series:
    """成交量相对均量。"""

    return volume / volume.rolling(window=window, min_periods=window).mean()


INDICATOR_REGISTRY: Dict[str, Callable[..., pd.Series]] = {
    "sma": sma,
    "ema": ema,
    "momentum": momentum,
    "roc": rate_of_change,
    "volatility": volatility,
    "volume_ratio": volume_ratio,
}


def get_indicator(name: str) -> Callable[..., pd.Series]:
    if name not in INDICATOR_REGISTRY:
        raise KeyError(f"未注册的指标：{name}")
    return INDICATOR_REGISTRY[name]
