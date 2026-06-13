"""pgvector similarity search — all similarity in PostgreSQL."""

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
    return [(int(r[0]), float(r[1])) for r in rows]
