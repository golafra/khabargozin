"""pgvector similarity search — all similarity in PostgreSQL."""

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings


OPEN_CLUSTER_STATUSES = ("pending", "scored", "ai_done")


def find_similar_clusters(
    session: Session,
    query_embedding: list[float],
    *,
    statuses: tuple[str, ...] = OPEN_CLUSTER_STATUSES,
    limit: int = 10,
    window_cutoff: Optional[datetime] = None,
) -> list[tuple[int, float]]:
    settings = get_settings()
    if window_cutoff is None:
        window_cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.CLUSTER_ACTIVE_WINDOW_MINUTES
        )

    vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
    ef_search = settings.PGVECTOR_EF_SEARCH
    session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))
    sql = text("""
        SELECT id, 1 - (centroid_embedding <=> CAST(:vec AS vector)) AS sim
        FROM clusters
        WHERE status = ANY(:statuses)
          AND centroid_embedding IS NOT NULL
          AND (window_start IS NULL OR window_start > :cutoff)
        ORDER BY centroid_embedding <=> CAST(:vec AS vector)
        LIMIT :lim
    """)
    rows = session.execute(
        sql,
        {
            "vec": vec_literal,
            "statuses": list(statuses),
            "cutoff": window_cutoff,
            "lim": limit,
        },
    ).fetchall()
    out: list[tuple[int, float]] = []
    for row in rows:
        sim = float(row[1])
        if math.isnan(sim) or math.isinf(sim):
            continue
        out.append((int(row[0]), sim))
    return out


def find_recent_published_similar(
    session: Session,
    query_embedding: list[float],
    *,
    hours: int | None = None,
    limit: int = 8,
) -> list[tuple[int, float]]:
    """Similar published clusters by publication time (not cluster window_start)."""
    settings = get_settings()
    if hours is None:
        hours = settings.DUPLICATE_PUBLISH_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    vec_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"
    sql = text("""
        SELECT c.id, 1 - (c.centroid_embedding <=> CAST(:vec AS vector)) AS sim
        FROM clusters c
        JOIN publications p ON p.cluster_id = c.id
        WHERE c.status = 'published'
          AND p.is_retracted IS FALSE
          AND p.published_at > :cutoff
          AND c.centroid_embedding IS NOT NULL
        ORDER BY c.centroid_embedding <=> CAST(:vec AS vector)
        LIMIT :lim
    """)
    rows = session.execute(
        sql,
        {"vec": vec_literal, "cutoff": cutoff, "lim": limit},
    ).fetchall()
    out: list[tuple[int, float]] = []
    for row in rows:
        sim = float(row[1])
        if math.isnan(sim) or math.isinf(sim):
            continue
        out.append((int(row[0]), sim))
    return out
