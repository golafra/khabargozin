"""Nightly cluster reconciliation task."""

from app.resilience.task_lock import acquire_redis_lock, release_redis_lock
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.reconcile.reconcile_clusters", acks_late=True)
def reconcile_clusters() -> dict:
    from app.config import get_settings
    from app.clustering.graph_cluster import reconcile_open_clusters
    from app.db.session import get_session

    settings = get_settings()
    lock_key = "task:reconcile_clusters"
    if not acquire_redis_lock(lock_key, settings.TASK_LOCK_TTL_CLUSTER_SECONDS):
        return {"skipped": True}

    session = get_session()
    try:
        result = reconcile_open_clusters(session)
        return result
    finally:
        session.close()
        release_redis_lock(lock_key)
