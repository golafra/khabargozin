"""Graph-based cluster reconciliation — phase 2."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clustering.confidence import update_cluster_confidence_metrics
from app.clustering.feature_store import FeatureStore
from app.clustering.merge import OPEN_STATUSES
from app.clustering.similarity import hybrid_similarity
from app.clustering.topic_windows import reconcile_lookback_hours
from app.config import get_settings
from app.db.models.cluster import Cluster
from app.db.models.message import Message


def _union_find(parent: dict[int, int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union(parent: dict[int, int], a: int, b: int) -> None:
    ra, rb = _union_find(parent, a), _union_find(parent, b)
    if ra != rb:
        parent[rb] = ra


def build_components(message_ids: list[int], edges: list[tuple[int, int]]) -> dict[int, list[int]]:
    parent = {mid: mid for mid in message_ids}
    for a, b in edges:
        if a in parent and b in parent:
            _union(parent, a, b)
    groups: dict[int, list[int]] = defaultdict(list)
    for mid in message_ids:
        groups[_union_find(parent, mid)].append(mid)
    return dict(groups)


def reconcile_open_clusters(session: Session) -> dict:
    """Batch graph CC on messages in open clusters within topic lookback."""
    settings = get_settings()
    store = FeatureStore()
    now = datetime.now(timezone.utc)

    clusters = session.scalars(
        select(Cluster).where(Cluster.status.in_(OPEN_STATUSES))
    ).all()

    splits = 0
    merges = 0
    for cluster in clusters:
        topic = cluster.topic or "general"
        cutoff = now - timedelta(hours=reconcile_lookback_hours(topic))
        messages = session.scalars(
            select(Message).where(
                Message.cluster_id == cluster.id,
                Message.is_deleted.is_(False),
                Message.published_at >= cutoff,
            )
        ).all()
        if len(messages) < 2:
            continue

        msg_map = {m.id: m for m in messages}
        edges: list[tuple[int, int]] = []
        ids = list(msg_map.keys())
        for i, id_a in enumerate(ids):
            fa = store.read(msg_map[id_a])
            for id_b in ids[i + 1 :]:
                fb = store.read(msg_map[id_b])
                hybrid = hybrid_similarity(msg_map[id_a], msg_map[id_b], fa, fb)
                if hybrid.should_merge and not hybrid.fingerprint_block:
                    edges.append((id_a, id_b))

        components = build_components(ids, edges)
        if len(components) <= 1:
            continue

        # multiple components in one cluster → split by reassigning to new clusters
        component_list = list(components.values())
        component_list.sort(key=len, reverse=True)
        primary_ids = set(component_list[0])
        for secondary in component_list[1:]:
            for mid in secondary:
                msg = msg_map[mid]
                old_cluster_id = msg.cluster_id
                msg.cluster_id = None
                session.flush()
                from app.clustering.merge import create_cluster_for_message
                from app.clustering.embedder import embedding_to_list

                emb = embedding_to_list(msg.embedding) or []
                create_cluster_for_message(session, msg, emb, store.read(msg))
                splits += 1
                if old_cluster_id:
                    update_cluster_confidence_metrics(session, old_cluster_id)

    session.commit()
    return {"splits": splits, "merges": merges, "clusters_scanned": len(clusters)}
