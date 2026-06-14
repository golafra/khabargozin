"""Read-only queries for admin dashboard."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.client import circuit_breaker_open
from app.config import get_settings
from app.db.models.ai_result import AIResult
from app.db.models.cluster import Cluster
from app.db.models.message import Message
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox
from app.db.models.source import Source


@dataclass
class DashboardStats:
    publish_mode: str
    messages_total: int = 0
    messages_unclustered: int = 0
    clusters_by_status: dict[str, int] = field(default_factory=dict)
    outbox_by_status: dict[str, int] = field(default_factory=dict)
    published_today: int = 0
    ai_failed: int = 0
    ai_ready: int = 0
    circuit_breaker: bool = False
    ai_cost_usd: float = 0.0
    ai_budget_usd: float = 15.0
    ai_budget_pct: float = 0.0
    stale_sources: list[Source] = field(default_factory=list)
    recent_publications: list[tuple[Publication, AIResult | None]] = field(default_factory=list)


def get_dashboard(session: Session) -> DashboardStats:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stale_cutoff = now - timedelta(minutes=settings.SOURCE_STALE_ALERT_MINUTES)

    stats = DashboardStats(
        publish_mode=settings.PUBLISH_MODE,
        ai_budget_usd=settings.OPENAI_MONTHLY_BUDGET_USD,
    )
    stats.messages_total = session.scalar(select(func.count()).select_from(Message)) or 0
    stats.messages_unclustered = session.scalar(
        select(func.count()).select_from(Message).where(Message.cluster_id.is_(None))
    ) or 0

    for status, count in session.execute(
        select(Cluster.status, func.count()).group_by(Cluster.status)
    ).all():
        stats.clusters_by_status[status] = count

    for status, count in session.execute(
        select(PublicationOutbox.status, func.count()).group_by(PublicationOutbox.status)
    ).all():
        stats.outbox_by_status[status] = count

    stats.published_today = session.scalar(
        select(func.count()).select_from(Publication).where(Publication.published_at >= today)
    ) or 0
    stats.ai_failed = stats.clusters_by_status.get("ai_failed", 0)
    stats.ai_ready = stats.clusters_by_status.get("ai_ready", 0)
    stats.circuit_breaker = circuit_breaker_open(session)

    stats.ai_cost_usd = float(
        session.scalar(
            select(func.coalesce(func.sum(AIResult.cost_estimate_usd), 0.0)).where(
                AIResult.created_at >= month_start
            )
        )
        or 0.0
    )
    if settings.OPENAI_MONTHLY_BUDGET_USD:
        stats.ai_budget_pct = stats.ai_cost_usd / settings.OPENAI_MONTHLY_BUDGET_USD * 100

    stats.stale_sources = list(
        session.scalars(
            select(Source).where(
                Source.is_active.is_(True),
                Source.last_successful_fetch_at < stale_cutoff,
            )
        ).all()
    )

    pubs = session.scalars(
        select(Publication).order_by(Publication.published_at.desc()).limit(10)
    ).all()
    for pub in pubs:
        ai = session.scalar(
            select(AIResult)
            .where(AIResult.cluster_id == pub.cluster_id)
            .order_by(AIResult.created_at.desc())
            .limit(1)
        )
        stats.recent_publications.append((pub, ai))

    return stats


def list_sources(session: Session) -> list[Source]:
    return list(session.scalars(select(Source).order_by(Source.username)).all())


def list_clusters(session: Session, status: str | None = None, limit: int = 80) -> list[Cluster]:
    q = select(Cluster).order_by(Cluster.updated_at.desc()).limit(limit)
    if status:
        q = q.where(Cluster.status == status)
    return list(session.scalars(q).all())


def get_cluster_detail(session: Session, cluster_id: int) -> dict | None:
    cluster = session.get(Cluster, cluster_id)
    if not cluster:
        return None

    messages = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .order_by(Message.published_at.asc())
    ).all()

    ai = session.scalar(
        select(AIResult)
        .where(AIResult.cluster_id == cluster_id)
        .order_by(AIResult.created_at.desc())
        .limit(1)
    )
    outbox = session.scalar(
        select(PublicationOutbox).where(PublicationOutbox.cluster_id == cluster_id)
    )
    pub = session.scalar(
        select(Publication).where(Publication.cluster_id == cluster_id)
    )

    return {
        "cluster": cluster,
        "messages": messages,
        "ai": ai,
        "outbox": outbox,
        "publication": pub,
    }


@dataclass
class PipelineTrace:
    """One cluster's journey through the pipeline (messages fetched in time window)."""

    cluster: Cluster
    messages: list[tuple[Message, Source]]
    messages_in_window: list[tuple[Message, Source]]
    ai: AIResult | None
    outbox: PublicationOutbox | None
    publication: Publication | None
    window_latest: datetime


@dataclass
class UnclusteredMessage:
    message: Message
    source: Source


def list_pipeline_traces(
    session: Session,
    hours: float = 3,
    limit: int = 50,
) -> tuple[list[PipelineTrace], list[UnclusteredMessage], datetime]:
    """Clusters with at least one message fetched (created_at) in the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    cluster_rows = session.execute(
        select(Message.cluster_id, func.max(Message.created_at).label("window_latest"))
        .where(Message.created_at >= since, Message.cluster_id.isnot(None))
        .group_by(Message.cluster_id)
        .order_by(func.max(Message.created_at).desc())
        .limit(limit)
    ).all()

    traces: list[PipelineTrace] = []
    for cluster_id, window_latest in cluster_rows:
        detail = get_cluster_detail(session, cluster_id)
        if not detail:
            continue
        in_window = [(m, s) for m, s in detail["messages"] if m.created_at >= since]
        if not in_window:
            continue
        traces.append(
            PipelineTrace(
                cluster=detail["cluster"],
                messages=detail["messages"],
                messages_in_window=in_window,
                ai=detail["ai"],
                outbox=detail["outbox"],
                publication=detail["publication"],
                window_latest=window_latest,
            )
        )

    unclustered_rows = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.created_at >= since, Message.cluster_id.is_(None))
        .order_by(Message.created_at.desc())
        .limit(30)
    ).all()
    unclustered = [UnclusteredMessage(message=m, source=s) for m, s in unclustered_rows]

    return traces, unclustered, since


def pipeline_step_status(trace: PipelineTrace) -> dict[str, str]:
    """Map pipeline stages to ok | pending | fail | skip for UI."""
    c = trace.cluster
    stages = {
        "fetch": "ok",
        "cluster": "ok" if c.id else "pending",
        "threshold": "skip",
        "ai": "pending",
        "outbox": "skip",
        "publish": "skip",
    }
    if c.status == "below_threshold":
        stages["threshold"] = "fail"
        stages["ai"] = "skip"
    elif c.status in ("scored", "ai_ready"):
        stages["threshold"] = "ok"
        stages["ai"] = "pending"
    elif c.status == "ai_failed":
        stages["threshold"] = "ok"
        stages["ai"] = "fail"
    elif c.status in ("ai_done", "hold", "published"):
        stages["threshold"] = "ok"
        stages["ai"] = "ok"
    if c.status == "hold":
        stages["outbox"] = "pending"
    if trace.outbox:
        if trace.outbox.status in ("sent", "dry_run"):
            stages["outbox"] = "ok"
        elif trace.outbox.status in ("pending", "sending"):
            stages["outbox"] = "pending"
        elif trace.outbox.status == "unknown":
            stages["outbox"] = "fail"
        else:
            stages["outbox"] = "pending"
    if trace.publication:
        stages["publish"] = "ok"
    elif trace.outbox and trace.outbox.status == "sent":
        stages["publish"] = "ok"
    elif trace.ai and trace.ai.status == "publish" and not trace.outbox:
        stages["outbox"] = "pending"
    return stages
