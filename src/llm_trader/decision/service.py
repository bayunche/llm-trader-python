"""决策结果持久化服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlmodel import Session, select

from llm_trader.db.models import (
    CheckerResult,
    Decision,
    DecisionAction,
    DecisionLedger,
    RiskResult,
)
from llm_trader.db.models.enums import (
    ActionType,
    CheckerResultStatus,
    OrderSide,
    OrderTimeInForce,
    OrderType,
    DecisionStatus,
    RiskPosture,
)
from llm_trader.db.session import create_session_factory

from .schema import ActorDecisionPayload, CheckerResultPayload


@dataclass
class DecisionRecord:
    decision: Decision
    checker_result: Optional[CheckerResult]
    risk_result: Optional[RiskResult] = None
    ledger: Optional[DecisionLedger] = None


class DecisionService:
    """封装 Decision/Action/CheckerResult 的写入逻辑。"""

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or create_session_factory()

    def record(
        self,
        *,
        observation_id: str,
        actor_result: ActorDecisionPayload,
        checker_result: Optional[CheckerResultPayload] = None,
    ) -> DecisionRecord:
        if not observation_id:
            observation_id = actor_result.observations_ref
        if not observation_id:
            raise ValueError("observation_id 不能为空")

        with self._session_factory() as session:
            decision = self._upsert_decision(session, observation_id, actor_result)
            stored_checker = self._upsert_checker(session, decision.decision_id, checker_result)
            session.commit()
            session.refresh(decision)
            if stored_checker is not None:
                session.refresh(stored_checker)
            return DecisionRecord(
                decision=decision,
                checker_result=stored_checker,
            )

    def _upsert_decision(
        self,
        session: Session,
        observation_id: str,
        payload: ActorDecisionPayload,
    ) -> Decision:
        existing = session.get(Decision, payload.decision_id)
        decision = existing or Decision(decision_id=payload.decision_id)
        decision.timestamp = payload.timestamp
        decision.observation_id = observation_id
        decision.account_nav = float(payload.account_view.get("nav", 0.0))
        decision.account_cash = float(payload.account_view.get("cash", 0.0))

        global_intent = payload.global_intent or {}
        posture_raw = global_intent.get("risk_posture")
        decision.global_intent_risk_posture = (
            RiskPosture(str(posture_raw)) if posture_raw else None
        )
        max_margin = global_intent.get("max_new_margin")
        decision.global_intent_max_new_margin = (
            float(max_margin) if max_margin is not None else None
        )
        decision.notes = payload.notes

        if not existing:
            session.add(decision)
            session.flush()
        else:
            # 清理旧的动作以避免重复
            actions = session.exec(
                select(DecisionAction).where(DecisionAction.decision_id == decision.decision_id)
            ).all()
            for action in actions:
                session.delete(action)
            session.flush()

        for action_payload in payload.actions:
            if not action_payload.symbol or not action_payload.type:
                continue
            try:
                action_type = ActionType(action_payload.type)
            except ValueError:
                action_type = ActionType.NO_OP
            side = None
            if action_payload.side:
                try:
                    side = OrderSide(action_payload.side)
                except ValueError:
                    side = None
            order_type = None
            if action_payload.order_type:
                try:
                    order_type = OrderType(action_payload.order_type)
                except ValueError:
                    order_type = None
            tif = None
            if action_payload.tif:
                try:
                    tif = OrderTimeInForce(action_payload.tif)
                except ValueError:
                    tif = None
            action = DecisionAction(
                decision_id=decision.decision_id,
                type=action_type,
                symbol=action_payload.symbol,
                side=side,
                order_type=order_type,
                price=action_payload.price,
                qty=action_payload.qty,
                tif=tif,
                target_order_id=action_payload.target_order_id,
                intent_rationale=action_payload.intent_rationale,
                intent_confidence=action_payload.intent_confidence,
            )
            session.add(action)
        session.flush()
        return decision

    def _upsert_checker(
        self,
        session: Session,
        decision_id: str,
        payload: Optional[CheckerResultPayload],
    ) -> Optional[CheckerResult]:
        if payload is None:
            existing = session.get(CheckerResult, decision_id)
            if existing:
                session.delete(existing)
            return None
        status = CheckerResultStatus.PASS if payload.passed else CheckerResultStatus.FAIL
        existing = session.get(CheckerResult, decision_id)
        record = existing or CheckerResult(decision_id=decision_id)
        record.status = status
        record.reasons = list(payload.reasons)
        if payload.checked_at is None:
            raise ValueError("checker_result.checked_at 不能为空")
        record.checked_at = payload.checked_at
        record.observation_expired = payload.observation_expired
        record.conflicts = list(payload.conflicts)
        if not existing:
            session.add(record)
        session.flush()
        return record

    def record_risk_result(
        self,
        *,
        decision_id: str,
        passed: bool,
        reasons: Optional[list] = None,
        corrections: Optional[list] = None,
        evaluated_at: Optional[datetime] = None,
    ) -> RiskResult:
        with self._session_factory() as session:
            existing = session.get(RiskResult, decision_id)
            record = existing or RiskResult(decision_id=decision_id)
            record.passed = passed
            record.reasons = list(reasons or [])
            record.corrections = list(corrections or [])
            record.evaluated_at = evaluated_at or datetime.now(tz=timezone.utc)
            if not existing:
                session.add(record)
            session.flush()
            session.refresh(record)
            session.commit()
            return record

    def record_ledger(
        self,
        *,
        decision_id: str,
        observation_id: str,
        actor_model: str,
        checker_model: Optional[str],
        status: DecisionStatus,
        risk_summary: Optional[Dict[str, object]] = None,
        actor_json_ref: Optional[str] = None,
        checker_json_ref: Optional[str] = None,
        executed_at: Optional[datetime] = None,
    ) -> DecisionLedger:
        with self._session_factory() as session:
            existing = session.get(DecisionLedger, decision_id)
            record = existing or DecisionLedger(decision_id=decision_id)
            record.observation_ref = observation_id
            record.actor_model = actor_model
            record.checker_model = checker_model or actor_model
            record.actor_json_ref = actor_json_ref
            record.checker_json_ref = checker_json_ref
            record.risk_summary = risk_summary or {}
            record.status = status
            now = datetime.now(tz=timezone.utc)
            if record.created_at is None:
                record.created_at = now
            record.executed_at = executed_at
            if not existing:
                session.add(record)
            session.flush()
            session.refresh(record)
            session.commit()
            return record


__all__ = ["DecisionService", "DecisionRecord"]
