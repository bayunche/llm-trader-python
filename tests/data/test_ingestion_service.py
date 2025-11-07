from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine, select

from llm_trader.data.ingestion import DataIngestionService
from llm_trader.db.models import AccountPosition, AccountSnapshot
from llm_trader.db.models.enums import RiskPosture


class DummyAccountPipeline:
    def __init__(self) -> None:
        self._called = False

    def fetch(self):
        self._called = True
        return {
            "captured_at": datetime(2024, 1, 1, 9, 30),
            "nav": 1_200_000.0,
            "cash": 500_000.0,
            "available": 450_000.0,
            "posture": RiskPosture.CAUTIOUS,
            "positions": [
                {"symbol": "600000.SH", "qty": 1000, "avg_price": 10.0, "market_value": 10500.0}
            ],
        }


def _session_factory(engine):
    @contextmanager
    def factory():
        with Session(engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
    return factory


def test_sync_account_snapshot_persists_payload() -> None:
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    pipeline = DummyAccountPipeline()
    service = DataIngestionService(session_factory=_session_factory(engine), account_pipeline=pipeline)

    payload = service.sync_account_snapshot()

    assert payload is not None
    assert pipeline._called is True
    with Session(engine) as session:
        snapshot = session.exec(select(AccountSnapshot)).one()
        assert snapshot.nav == 1_200_000.0
        positions = session.exec(select(AccountPosition)).all()
        assert len(positions) == 1
        assert positions[0].symbol == "600000.SH"
