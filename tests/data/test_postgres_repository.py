from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine

from llm_trader.data.repositories.postgres import PostgresDataRepository
from llm_trader.db.models import AccountSnapshot, MasterSymbol, RealtimeQuote
from llm_trader.db.models.enums import RiskPosture


def create_sqlite_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


def test_upsert_and_list_master_symbols():
    engine = create_sqlite_engine()
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
        session.commit()

    with Session(engine) as session:
        rows = session.query(MasterSymbol).all()
        assert len(rows) == 1
        repo = PostgresDataRepository(session)
        symbols = repo.list_active_symbols()
        assert symbols == ["600000.SH"]


def test_upsert_realtime_quotes():
    engine = create_sqlite_engine()
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
        session.commit()

    with Session(engine) as session:
        quote = session.query(RealtimeQuote).first()
        assert quote is not None
        assert quote.symbol == "600000.SH"


def test_store_account_snapshot_and_positions():
    engine = create_sqlite_engine()
    captured = datetime.utcnow()
    with Session(engine) as session:
        repo = PostgresDataRepository(session)
        repo.store_account_snapshot(
            captured_at=captured,
            nav=1000000.0,
            cash=500000.0,
            available=400000.0,
            posture=RiskPosture.CAUTIOUS,
            positions=[
                {"symbol": "600000.SH", "qty": 1000, "avg_price": 10.0, "market_value": 10500},
            ],
        )
        session.commit()

    with Session(engine) as session:
        snapshot = session.query(AccountSnapshot).first()
        assert snapshot is not None
        assert snapshot.risk_posture == RiskPosture.CAUTIOUS
