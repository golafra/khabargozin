"""Integration test fixtures — real Postgres."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://khabargozin:khabargozin@localhost:5432/khabargozin_test",
)


def _db_reachable(url: str) -> bool:
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_reachable(TEST_DB_URL),
    reason="integration DB not available — run scripts/setup_test_db.py",
)


@pytest.fixture
def db_session(monkeypatch):
    """App session bound to khabargozin_test; rolls back after each test."""
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("PUBLISH_MODE", "dry_run")

    from app.config import get_settings
    from app.db import session as db_session_mod

    get_settings.cache_clear()
    db_session_mod.get_engine.cache_clear()
    db_session_mod.get_session_factory.cache_clear()

    session = db_session_mod.get_session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        get_settings.cache_clear()
        db_session_mod.get_engine.cache_clear()
        db_session_mod.get_session_factory.cache_clear()


@pytest.fixture
def raw_db_session():
    """Direct SQLAlchemy session (no app settings) for low-level SQL tests."""
    engine = create_engine(TEST_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
