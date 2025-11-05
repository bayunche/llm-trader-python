from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, SQLModel, create_engine, select

from llm_trader.db.models import Observation

from llm_trader.data.repositories.postgres import PostgresDataRepository
from llm_trader.observation import ObservationBuilder
from llm_trader.db.models.enums import RiskPosture


def create_engine_and_seed():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        repo = PostgresDataRepository(session)
        repo.upsert_master_symbols(
            [
                {
                    "symbol": "600000.SH",
                    "exchange": "SH",
                    "board": "主板",
                    "name": "浦发银行",
                    "is_st": False,
                    "listed_date": datetime(1999, 11, 10).date(),
                    "industry": "银行",
                    "market_cap": 1000000000.0,
                    "float_cap": 800000000.0,
                    "pe_ttm": 8.5,
                    "pb": 0.9,
                    "tick_size": 0.01,
                    "lot_size": 100,
                    "status": "active",
                    "as_of_date": datetime.utcnow().date(),
                    "version": 1,
                }
            ]
        )
        repo.upsert_realtime_quotes(
            [
                {
                    "symbol": "600000.SH",
                    "name": "浦发银行",
                    "last_price": 10.5,
                    "change": 0.2,
                    "change_ratio": 1.5,
                    "volume": 1000000,
                    "amount": 10500000,
                    "snapshot_time": datetime.utcnow(),
                }
            ]
        )
        repo.store_account_snapshot(
            captured_at=datetime.utcnow(),
            nav=1000000.0,
            cash=500000.0,
            available=400000.0,
            posture=RiskPosture.NORMAL,
            positions=[
                {"symbol": "600000.SH", "qty": 1000, "avg_price": 10.0, "market_value": 10500},
            ],
        )
        session.commit()
    return engine


class FakeRedis:
    def __init__(self) -> None:
        self._store: Dict[str, tuple[str, datetime]] = {}

    def setex(self, name: str, time: int, value: str) -> None:
        expires = datetime.utcnow() + timedelta(seconds=time)
        self._store[name] = (value, expires)

    def get(self, name: str) -> Optional[str]:
        record = self._store.get(name)
        if not record:
            return None
        value, expires = record
        if datetime.utcnow() >= expires:
            self._store.pop(name, None)
            return None
        return value


def test_observation_builder_creates_record():
    engine = create_engine_and_seed()

    @contextmanager
    def session_factory():
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    builder = ObservationBuilder(session_factory=session_factory, symbol_universe_limit=10)
    payload = builder.build()
    assert payload.universe
    assert "600000.SH" in payload.features
    assert payload.account["nav"] > 0

    with Session(engine) as session:
        count = session.exec(select(func.count()).select_from(Observation)).one()
        assert count == 1


def test_observation_builder_uses_cache(monkeypatch) -> None:
    engine = create_engine_and_seed()

    @contextmanager
    def session_factory():
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    redis_client = FakeRedis()
    builder = ObservationBuilder(
        session_factory=session_factory,
        redis_client=redis_client,
        symbol_universe_limit=10,
        valid_ttl_ms=5000,
    )
    first = builder.build()
    second = builder.build()
    assert first.observation_id == second.observation_id
    metrics = builder.cache_metrics
    assert metrics["hits"] >= 1
    assert metrics["misses"] >= 1
    with Session(engine) as session:
        count = session.exec(select(func.count()).select_from(Observation)).one()
        assert count == 1
