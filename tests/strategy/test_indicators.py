"""指标库测试。"""

from __future__ import annotations

import pandas as pd

from llm_trader.strategy.library.indicators import ema, momentum, sma, volatility


def test_sma_basic() -> None:
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, window=3)
    assert result.iloc[-1] == 4


def test_ema_basic() -> None:
    series = pd.Series([1, 2, 3, 4, 5])
    result = ema(series, span=3)
    assert round(result.iloc[-1], 2) > 4.0


def test_momentum() -> None:
    series = pd.Series([10, 11, 12, 13])
    result = momentum(series, window=2)
    assert result.iloc[-1] == 2


def test_volatility() -> None:
    series = pd.Series([10, 10.5, 11, 10.8, 10.6])
    result = volatility(series, window=2)
    assert result.iloc[-1] >= 0
