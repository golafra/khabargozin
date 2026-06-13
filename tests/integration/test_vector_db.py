"""pgvector integration — real cosine search."""

import pytest
from sqlalchemy import text

from tests.integration.conftest import requires_db

pytestmark = requires_db


def test_pgvector_cosine_search(raw_db_session):
    raw_db_session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    raw_db_session.execute(text("""
        CREATE TEMP TABLE tmp_vec_clusters (
            id serial PRIMARY KEY,
            centroid_embedding vector(3)
        ) ON COMMIT DROP
    """))
    raw_db_session.execute(
        text("INSERT INTO tmp_vec_clusters (centroid_embedding) VALUES (CAST(:v AS vector))"),
        {"v": "[1,0,0]"},
    )
    raw_db_session.execute(
        text("INSERT INTO tmp_vec_clusters (centroid_embedding) VALUES (CAST(:v AS vector))"),
        {"v": "[0.9,0.1,0]"},
    )
    raw_db_session.execute(
        text("INSERT INTO tmp_vec_clusters (centroid_embedding) VALUES (CAST(:v AS vector))"),
        {"v": "[0,1,0]"},
    )
    rows = raw_db_session.execute(
        text("""
            SELECT id, 1 - (centroid_embedding <=> CAST(:q AS vector)) AS sim
            FROM tmp_vec_clusters
            ORDER BY centroid_embedding <=> CAST(:q AS vector)
            LIMIT 2
        """),
        {"q": "[1,0,0]"},
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][0] == 1
    assert rows[0][1] > 0.99


def test_find_similar_clusters_integration(db_session):
    from datetime import datetime, timezone

    from app.clustering.vector_search import find_similar_clusters
    from app.db.models.cluster import Cluster

    c1 = Cluster(
        status="scored",
        centroid_embedding=[1.0, 0.0, 0.0] + [0.0] * 381,
        window_start=datetime.now(timezone.utc),
        independent_source_count=1,
    )
    c2 = Cluster(
        status="scored",
        centroid_embedding=[0.0, 1.0, 0.0] + [0.0] * 381,
        window_start=datetime.now(timezone.utc),
        independent_source_count=1,
    )
    db_session.add_all([c1, c2])
    db_session.flush()

    query = [1.0, 0.0, 0.0] + [0.0] * 381
    results = find_similar_clusters(db_session, query, statuses=("scored",), limit=3)
    assert results
    assert results[0][0] == c1.id
    assert results[0][1] > 0.9
