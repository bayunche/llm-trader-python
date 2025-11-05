from __future__ import annotations

"""
观测构建服务：聚合主表、行情、账户与风险信息，写入 Observation 表。
"""

import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, ContextManager, Dict, List, Optional, Sequence

import pendulum
from redis import Redis
from sqlmodel import Session

from llm_trader.common import get_logger
from llm_trader.data.repositories.postgres import PostgresDataRepository
from llm_trader.db.models import Observation
from llm_trader.db.models.enums import ClockPhase, RiskPosture

_LOGGER = get_logger("observation.builder")

SessionFactory = Callable[[], ContextManager[Session]]


@dataclass(slots=True)
class ObservationPayload:
    """观测输出结构。"""

    observation_id: str
    generated_at: datetime
    valid_ttl_ms: int
    clock: Dict[str, Any]
    account: Dict[str, Any]
    positions: List[Dict[str, Any]]
    universe: List[str]
    features: Dict[str, Dict[str, Any]]
    market_rules: Dict[str, Dict[str, Any]]
    risk_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "generated_at": self.generated_at.isoformat(),
            "valid_ttl_ms": self.valid_ttl_ms,
            "clock": self.clock,
            "account": self.account,
            "positions": self.positions,
            "universe": self.universe,
            "features": self.features,
            "market_rules": self.market_rules,
            "risk_snapshot": self.risk_snapshot,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservationPayload":
        generated_at_raw = data.get("generated_at")
        generated_at = (
            datetime.fromisoformat(generated_at_raw) if isinstance(generated_at_raw, str) else datetime.utcnow()
        )
        return cls(
            observation_id=data["observation_id"],
            generated_at=generated_at,
            valid_ttl_ms=int(data.get("valid_ttl_ms", 3000)),
            clock=data.get("clock", {}),
            account=data.get("account", {}),
            positions=data.get("positions", []),
            universe=data.get("universe", []),
            features=data.get("features", {}),
            market_rules=data.get("market_rules", {}),
            risk_snapshot=data.get("risk_snapshot", {}),
        )


class ObservationBuilder:
    """负责构建并持久化 Observation。"""

    def __init__(
        self,
        session_factory: SessionFactory,
        *,
        redis_client: Optional[Redis] = None,
        valid_ttl_ms: int = 3000,
        symbol_universe_limit: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis_client
        self._valid_ttl_ms = valid_ttl_ms
        self._symbol_universe_limit = symbol_universe_limit
        self._latest_cache_key = "observation:latest"
        self._cache_hits = 0
        self._cache_misses = 0

    @contextmanager
    def _repository(self) -> Sequence[PostgresDataRepository]:
        with self._session_factory() as session:
            yield PostgresDataRepository(session), session

    def build(self) -> ObservationPayload:
        """聚合数据并返回观测。"""
        cached = self._load_cached()
        if cached:
            self._cache_hits += 1
            _LOGGER.info(
                "返回缓存观测",
                extra={"observation_id": cached.observation_id, "symbols": len(cached.universe)},
            )
            return cached
        self._cache_misses += 1

        with self._repository() as (repo, session):
            observation_id = uuid.uuid4().hex
            generated_at = datetime.utcnow()
            universe = repo.list_active_symbols(limit=self._symbol_universe_limit)
            if not universe:
                raise RuntimeError("观测构建失败：数据库中缺少活跃标的，请先同步主表。")
            features = repo.to_universe_features(symbols=universe)
            market_rules = self._build_market_rules(repo, universe)
            account_snapshot = repo.latest_account_snapshot()
            positions_payload = repo.to_position_payload()
            if account_snapshot:
                account_payload = {
                    "nav": account_snapshot.nav,
                    "cash": account_snapshot.cash,
                    "available": account_snapshot.available,
                    "risk_posture": account_snapshot.risk_posture.value,
                }
                risk_posture = account_snapshot.risk_posture
            else:
                account_payload = {"nav": 0.0, "cash": 0.0, "available": 0.0, "risk_posture": RiskPosture.NORMAL.value}
                risk_posture = RiskPosture.NORMAL

            payload = ObservationPayload(
                observation_id=observation_id,
                generated_at=generated_at,
                valid_ttl_ms=self._valid_ttl_ms,
                clock={"phase": self._detect_clock_phase()},
                account=account_payload,
                positions=positions_payload,
                universe=universe,
                features=features,
                market_rules=market_rules,
                risk_snapshot={"posture": risk_posture.value},
            )

            self._persist(session, payload)
            self._cache(payload)
            _LOGGER.info("观测已构建并落库", extra={"observation_id": observation_id, "symbols": len(universe)})
            return payload

    def _persist(self, session: Session, payload: ObservationPayload) -> None:
        observation = Observation(
            observation_id=payload.observation_id,
            generated_at=payload.generated_at,
            valid_ttl_ms=payload.valid_ttl_ms,
            clock_phase=payload.clock["phase"],
            account_nav=float(payload.account.get("nav") or 0.0),
            account_cash=float(payload.account.get("cash") or 0.0),
            account_risk_posture=RiskPosture(payload.account.get("risk_posture", RiskPosture.NORMAL.value)),
            positions=payload.positions,
            universe=payload.universe,
            features=payload.features,
            market_rules=payload.market_rules,
            risk_snapshot=payload.risk_snapshot,
        )
        session.add(observation)

    def _cache(self, payload: ObservationPayload) -> None:
        if not self._redis:
            return
        ttl_seconds = max(int(self._valid_ttl_ms / 1000), 1)
        key = f"observation:{payload.observation_id}"
        self._redis.setex(name=key, time=ttl_seconds, value=payload.to_json())
        self._redis.setex(name=self._latest_cache_key, time=ttl_seconds, value=payload.to_json())

    def _load_cached(self) -> Optional[ObservationPayload]:
        if not self._redis:
            return None
        raw = self._redis.get(self._latest_cache_key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            payload = ObservationPayload.from_dict(data)
        except Exception:  # pragma: no cover - 缓存损坏直接忽略
            return None
        elapsed = datetime.utcnow() - payload.generated_at
        if elapsed.total_seconds() * 1000 >= payload.valid_ttl_ms:
            return None
        return payload

    @property
    def cache_metrics(self) -> Dict[str, int]:
        """返回缓存命中统计。"""

        return {"hits": self._cache_hits, "misses": self._cache_misses}

    def _build_market_rules(
        self,
        repo: PostgresDataRepository,
        symbols: Sequence[str],
    ) -> Dict[str, Dict[str, Any]]:
        master_map = repo.get_master_symbol_map(symbols)
        rules: Dict[str, Dict[str, Any]] = {}
        for symbol, master in master_map.items():
            rules[symbol] = {
                "tick_size": master.tick_size,
                "lot_size": master.lot_size,
                "price_band": {
                    "up": None,
                    "down": None,
                },
            }
        return rules

    def _detect_clock_phase(self) -> ClockPhase:
        """根据北京时间推断交易时钟阶段。"""
        now = pendulum.now("Asia/Shanghai")
        morning_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        lunch_start = now.replace(hour=11, minute=30, second=0, microsecond=0)
        afternoon_open = now.replace(hour=13, minute=0, second=0, microsecond=0)
        close = now.replace(hour=15, minute=0, second=0, microsecond=0)

        if now < morning_open:
            return ClockPhase.PRE_OPEN
        if morning_open <= now <= lunch_start:
            return ClockPhase.CONTINUOUS_TRADING
        if lunch_start < now < afternoon_open:
            return ClockPhase.OFF_MARKET
        if afternoon_open <= now <= close:
            return ClockPhase.CONTINUOUS_TRADING
        return ClockPhase.CLOSE
