"""交易风险控制策略。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from llm_trader.common import get_logger


@dataclass
class RiskThresholds:
    """风险阈值配置。"""

    max_equity_drawdown: float = 0.1  # 相对最大权益的回撤比
    max_position_ratio: float = 0.3  # 单标的占比上限


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
    ) -> None:
        self.thresholds = thresholds
        self._logger = get_logger("trading.risk")
        self._alert_callback = alert_callback or self._default_alert

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
        exposure_alerts = self._check_position_exposure(equity_series, positions)
        alerts.extend(exposure_alerts)

        if alerts:
            for message in alerts:
                self._alert_callback(message, {"alerts": alerts})
            return RiskDecision(proceed=False, alerts=alerts)
        return RiskDecision(proceed=True, alerts=[])

    def _default_alert(self, message: str, details: Dict[str, object]) -> None:
        self._logger.warning(message, extra={"details": details})

    def _normalize_equity(self, equity_curve: List[Dict[str, object]]) -> List[Tuple[float, float]]:
        series: List[Tuple[float, float]] = []
        for item in equity_curve:
            equity = item.get("equity")
            if equity is None:
                continue
            timestamp = item.get("timestamp") or item.get("date")
            try:
                equity_value = float(equity)
            except (TypeError, ValueError):
                continue
            if timestamp is None:
                series.append((len(series), equity_value))
            else:
                series.append((timestamp, equity_value))
        return series

    def _check_drawdown(self, series: List[Tuple[object, float]]) -> Optional[str]:
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

    def _check_position_exposure(
        self,
        equity_series: List[Tuple[object, float]],
        positions: List[Dict[str, object]],
    ) -> List[str]:
        if not positions or not equity_series:
            return []
        latest_equity = equity_series[-1][1]
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


__all__ = ["RiskPolicy", "RiskThresholds", "RiskDecision"]
