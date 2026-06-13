"""Integration test fixtures — real Postgres."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

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
