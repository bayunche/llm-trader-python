"""交易风险控制策略。"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from llm_trader.common import get_logger


@dataclass
class RiskThresholds:
    """风险阈值配置。"""

    max_equity_drawdown: float = 0.1  # 相对最大权益的回撤比
    max_position_ratio: float = 0.3  # 单标的占比上限
    max_equity_volatility: float = 0.0  # 权益波动率上限（0 表示禁用）
    max_sector_exposure: float = 0.0  # 行业敞口上限
    max_holding_days: int = 0  # 持仓时间限制（0 表示禁用）


@dataclass
class RiskDecision:
    """风险评估结果。"""

    proceed: bool
    alerts: List[str] = field(default_factory=list)


class RiskPolicy:
    """基于阈值的风险策略，用于在交易执行后评估是否需要暂停。"""

    def __init__(
        self,
        thresholds: RiskThresholds,
        alert_callback: Optional[Callable[[str, Dict[str, object]], None]] = None,
        sector_lookup: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        self.thresholds = thresholds
        self._logger = get_logger("trading.risk")
        self._alert_callback = alert_callback or self._default_alert
        self._sector_lookup = sector_lookup or (lambda _symbol: "UNKNOWN")

    def evaluate(
        self,
        equity_curve: List[Dict[str, object]],
        positions: List[Dict[str, object]],
    ) -> RiskDecision:
        alerts: List[str] = []
        equity_series = self._normalize_equity(equity_curve)
        if equity_series:
            drawdown_alert = self._check_drawdown(equity_series)
            if drawdown_alert:
                alerts.append(drawdown_alert)
            volatility_alert = self._check_volatility(equity_series)
            if volatility_alert:
                alerts.append(volatility_alert)
        exposure_alerts = self._check_position_exposure(equity_series, positions)
        alerts.extend(exposure_alerts)
        sector_alerts = self._check_sector_concentration(equity_series, positions)
        alerts.extend(sector_alerts)
        holding_alerts = self._check_holding_period(equity_series, positions)
        alerts.extend(holding_alerts)

        if alerts:
            for message in alerts:
                self._alert_callback(message, {"alerts": alerts})
            return RiskDecision(proceed=False, alerts=alerts)
        return RiskDecision(proceed=True, alerts=[])

    def _default_alert(self, message: str, details: Dict[str, object]) -> None:
        self._logger.warning(message, extra={"details": details})

    def _normalize_equity(self, equity_curve: List[Dict[str, object]]) -> List[Tuple[object, float]]:
        series: List[Tuple[object, float]] = []
        for item in equity_curve:
            equity = item.get("equity")
            if equity is None:
                continue
            timestamp = item.get("timestamp") or item.get("date")
            try:
                equity_value = float(equity)
            except (TypeError, ValueError):
                continue
            series.append((timestamp if timestamp is not None else len(series), equity_value))
        return series

    def _check_drawdown(self, series: List[Tuple[object, float]]) -> Optional[str]:
        if self.thresholds.max_equity_drawdown <= 0:
            return None
        max_equity = max(value for _, value in series)
        latest_equity = series[-1][1]
        if max_equity <= 0:
            return None
        drawdown = (max_equity - latest_equity) / max_equity
        if drawdown >= self.thresholds.max_equity_drawdown:
            percentage = drawdown * 100
            limit = self.thresholds.max_equity_drawdown * 100
            return f"最大回撤 {percentage:.2f}% 超过阈值 {limit:.2f}%"
        return None

    def _check_volatility(self, series: List[Tuple[object, float]]) -> Optional[str]:
        threshold = self.thresholds.max_equity_volatility
        if threshold <= 0 or len(series) < 3:
            return None
        returns: List[float] = []
        previous = series[0][1]
        for _, value in series[1:]:
            if previous == 0:
                previous = value
                continue
            try:
                ratio = (value - previous) / previous
            except (TypeError, ValueError):
                previous = value
                continue
            returns.append(ratio)
            previous = value
        if len(returns) < 2:
            return None
        volatility = statistics.stdev(returns)
        if volatility >= threshold:
            return f"权益波动率 {volatility:.2%} 超过阈值 {threshold:.2%}"
        return None

    def _check_position_exposure(
        self,
        equity_series: List[Tuple[object, float]],
        positions: List[Dict[str, object]],
    ) -> List[str]:
        if not positions or not equity_series or self.thresholds.max_position_ratio <= 0:
            return []
        latest_equity = self._resolve_latest_equity(equity_series)
        if latest_equity <= 0:
            return []
        alerts: List[str] = []
        for position in positions:
            symbol = position.get("symbol", "UNKNOWN")
            volume = position.get("volume")
            cost_price = position.get("cost_price")
            if volume is None or cost_price is None:
                continue
            try:
                notion = float(volume) * float(cost_price)
            except (TypeError, ValueError):
                continue
            ratio = notion / latest_equity
            if ratio >= self.thresholds.max_position_ratio:
                percentage = ratio * 100
                limit = self.thresholds.max_position_ratio * 100
                alerts.append(
                    f"标的 {symbol} 仓位占比 {percentage:.2f}% 超过阈值 {limit:.2f}%"
                )
        return alerts

    def _check_sector_concentration(
        self,
        equity_series: List[Tuple[object, float]],
        positions: List[Dict[str, object]],
    ) -> List[str]:
        threshold = self.thresholds.max_sector_exposure
        if threshold <= 0 or not positions or not equity_series:
            return []
        latest_equity = self._resolve_latest_equity(equity_series)
        if latest_equity <= 0:
            return []

        exposures: Dict[str, float] = defaultdict(float)
        for position in positions:
            symbol = position.get("symbol")
            volume = position.get("volume")
            cost_price = position.get("cost_price")
            if symbol is None or volume is None or cost_price is None:
                continue
            try:
                notion = float(volume) * float(cost_price)
            except (TypeError, ValueError):
                continue
            sector = self._sector_lookup(str(symbol)) or "UNKNOWN"
            exposures[sector] += notion

        alerts: List[str] = []
        for sector, notion in exposures.items():
            ratio = notion / latest_equity
            if ratio >= threshold:
                alerts.append(
                    f"行业 {sector} 敞口 {ratio:.2%} 超过阈值 {threshold:.2%}"
                )
        return alerts

    def _check_holding_period(
        self,
        equity_series: List[Tuple[object, float]],
        positions: List[Dict[str, object]],
    ) -> List[str]:
        max_days = self.thresholds.max_holding_days
        if max_days <= 0 or not positions:
            return []
        reference_time = self._resolve_evaluation_time(equity_series)
        if reference_time is None:
            return []
        alerts: List[str] = []
        for position in positions:
            symbol = position.get("symbol", "UNKNOWN")
            lots = position.get("lots") or []
            for lot in lots:
                acquired_at = lot.get("acquired_at")
                acquired_dt = self._parse_datetime(acquired_at)
                if acquired_dt is None:
                    continue
                if reference_time - acquired_dt > timedelta(days=max_days):
                    days = (reference_time - acquired_dt).days
                    alerts.append(
                        f"标的 {symbol} 持仓已 {days} 天超过阈值 {max_days} 天"
                    )
                    break
        return alerts

    def _resolve_latest_equity(self, series: List[Tuple[object, float]]) -> float:
        for _, value in reversed(series):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    def _resolve_evaluation_time(self, series: List[Tuple[object, float]]) -> Optional[datetime]:
        for timestamp, _ in reversed(series):
            candidate = self._parse_datetime(timestamp)
            if candidate is not None:
                return candidate
        return datetime.utcnow()

    @staticmethod
    def _parse_datetime(value: object) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None


__all__ = ["RiskPolicy", "RiskThresholds", "RiskDecision"]
