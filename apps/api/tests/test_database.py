"""Real-PostgreSQL tests for the SQLAlchemy database layer.

Requires the Docker PostgreSQL to be running and DATABASE_URL to be set
(see .env.example).
"""

import pytest
from sqlalchemy import text

from app.db.dependencies import get_db
from app.db.session import SessionLocal, engine


def test_engine_is_created() -> None:
    assert engine is not None


def test_engine_connects_and_selects_one() -> None:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_session_factory_executes_select_one() -> None:
    db = SessionLocal()
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
    finally:
        db.close()


def test_get_db_yields_session_and_closes_it() -> None:
    generator = get_db()
    db = next(generator)
    try:
        assert db.execute(text("SELECT 1")).scalar() == 1
        assert db.in_transaction() is True
    finally:
        with pytest.raises(StopIteration):
            next(generator)
    assert db.in_transaction() is False
    assert db.get_transaction() is None


def test_pool_returns_connections_after_session_close() -> None:
    baseline = engine.pool.checkedout()
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    assert engine.pool.checkedout() == baseline
