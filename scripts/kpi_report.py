"""KPI report — metrics, token cost, stale sources."""

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.ai.client import circuit_breaker_open
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.audit_log import AuditLog
from app.db.models.cluster import Cluster
from app.db.models.publication import Publication
from app.db.models.source import Source
from app.db.session import get_session
from scripts._util import configure_stdout


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="today")
    args = parser.parse_args()

    settings = get_settings()
    session = get_session()
    try:
        now = datetime.now(timezone.utc)
        if args.date == "today":
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            since = now - timedelta(days=7)

        total_clusters = session.scalar(
            select(func.count()).select_from(Cluster).where(Cluster.created_at >= since)
        ) or 0
        rejected = session.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.reason.in_(("below_threshold", "ai_reject")),
                AuditLog.created_at >= since,
            )
        ) or 0
        published = session.scalar(
            select(func.count()).select_from(Publication).where(Publication.published_at >= since)
        ) or 0
        multi_source = session.scalar(
            select(func.count()).select_from(Cluster).where(
                Cluster.independent_source_count > 1,
                Cluster.status == "published",
                Cluster.updated_at >= since,
            )
        ) or 0
        single_merge = session.scalar(
            select(func.count()).select_from(Cluster).where(
                Cluster.distinct_sources > 1,
                Cluster.independent_source_count == 1,
                Cluster.created_at >= since,
            )
        ) or 0

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        token_cost = session.scalar(
            select(func.coalesce(func.sum(AIResult.cost_estimate_usd), 0.0)).where(
                AIResult.created_at >= month_start
            )
        ) or 0.0
        prompt_tokens = session.scalar(
            select(func.coalesce(func.sum(AIResult.prompt_tokens), 0)).where(
                AIResult.created_at >= month_start
            )
        ) or 0
        completion_tokens = session.scalar(
            select(func.coalesce(func.sum(AIResult.completion_tokens), 0)).where(
                AIResult.created_at >= month_start
            )
        ) or 0

        stale_cutoff = now - timedelta(minutes=settings.SOURCE_STALE_ALERT_MINUTES)
        stale_sources = session.scalars(
            select(Source).where(
                Source.is_active.is_(True),
                Source.last_successful_fetch_at < stale_cutoff,
            )
        ).all()

        fast_count = session.scalar(
            select(func.count()).select_from(Publication).where(
                Publication.track == "fast", Publication.published_at >= since
            )
        ) or 0
        batch_count = session.scalar(
            select(func.count()).select_from(Publication).where(
                Publication.track == "batch", Publication.published_at >= since
            )
        ) or 0

        print("=== Khabargozin KPI Report ===")
        print(f"Period since: {since.isoformat()}")
        print(f"\nClusters created: {total_clusters}")
        print(f"Rejected/filtered: {rejected}")
        print(f"Published: {published} (fast={fast_count}, batch={batch_count})")
        print(f"Multi-source published: {multi_source}")
        print(f"Merged but single-independent (over-merge signal): {single_merge}")

        print(f"\n--- AI Cost (month) ---")
        print(f"Tokens: {prompt_tokens} prompt + {completion_tokens} completion")
        print(f"Cost estimate: ${float(token_cost):.4f} / ${settings.OPENAI_MONTHLY_BUDGET_USD}")
        if circuit_breaker_open(session):
            print("⚠ Circuit breaker ACTIVE")

        if stale_sources:
            print(f"\n⚠ Stale sources ({len(stale_sources)}):")
            for s in stale_sources:
                print(f"  @{s.username} last_fetch={s.last_successful_fetch_at}")

        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
