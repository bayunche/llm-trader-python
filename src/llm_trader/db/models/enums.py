from __future__ import annotations

"""
数据库使用的枚举常量，统一管理字符串取值。
"""

from enum import Enum


class ClockPhase(str, Enum):
    """交易时钟阶段。"""

    PRE_OPEN = "pre_open"
    CONTINUOUS_TRADING = "continuous_trading"
    CLOSE = "close"
    OFF_MARKET = "off_market"


class RiskPosture(str, Enum):
    """风险姿态枚举。"""

    NORMAL = "normal"
    CAUTIOUS = "cautious"
    FLAT_ONLY = "flat_only"
    KILL_SWITCH = "kill_switch"


class ActionType(str, Enum):
    """Actor 支持的动作类型。"""

    PLACE_ORDER = "place_order"
    MODIFY_ORDER = "modify_order"
    CANCEL_ORDER = "cancel_order"
    NO_OP = "no_op"


class OrderSide(str, Enum):
    """委托方向。"""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """委托类型。"""

    LIMIT = "limit"
    MARKET = "market"


class OrderTimeInForce(str, Enum):
    """时效策略。"""

    DAY = "day"
    IOC = "ioc"
    FOK = "fok"


class OrderStatus(str, Enum):
    """订单状态机枚举。"""

    CREATED = "created"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class DecisionStatus(str, Enum):
    """决策最终状态。"""

    EXECUTED = "executed"
    REJECTED_CHECKER = "rejected_checker"
    REJECTED_RISK = "rejected_risk"
    CANCELED = "canceled"


class CheckerResultStatus(str, Enum):
    """审单结果标记。"""

    PASS = "pass"
    FAIL = "fail"


class ModelRole(str, Enum):
    """模型角色区分。"""

    ACTOR = "actor"
    CHECKER = "checker"


class TradingMode(str, Enum):
    """统一启动模式。"""

    SHADOW = "shadow"
    COPILOT = "copilot"
    AUTOPILOT_STRICT = "autopilot_strict"
