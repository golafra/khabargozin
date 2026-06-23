"""Celery application."""

from celery import Celery
from celery.signals import worker_process_init, worker_ready

from app.config import get_settings

settings = get_settings()

celery_app = Celery("khabargozin", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=settings.CELERY_MAX_TASKS_PER_CHILD,
    task_default_queue="default",
    task_routes={
        "app.tasks.cluster.cluster_pending_messages": {"queue": "ml"},
    },
)


def build_schedule_from_settings(s: "Settings") -> dict:
    return {
        "fetch-all": {
            "task": "app.tasks.fetch.dispatch_fetch",
            "schedule": s.BEAT_FETCH_INTERVAL_SECONDS,
        },
        "cluster-pending": {
            "task": "app.tasks.cluster.dispatch_cluster",
            "schedule": s.BEAT_CLUSTER_INTERVAL_SECONDS,
        },
        "process-ai": {
            "task": "app.tasks.ai.process_cloud_ai",
            "schedule": s.BEAT_AI_INTERVAL_SECONDS,
        },
        "publish-batch": {
            "task": "app.tasks.publish.publish_batch_queue",
            "schedule": s.BEAT_BATCH_PUBLISH_INTERVAL_SECONDS,
        },
        "source-health": {
            "task": "app.tasks.fetch.check_source_health",
            "schedule": s.BEAT_SOURCE_HEALTH_INTERVAL_SECONDS,
        },
        "hold-check": {
            "task": "app.tasks.publish.check_hold_confirmations",
            "schedule": s.BEAT_HOLD_CHECK_INTERVAL_SECONDS,
        },
        "archive-weekly": {
            "task": "app.tasks.archive.archive_old_records",
            "schedule": 604800,
        },
    }


celery_app.conf.beat_schedule = build_schedule_from_settings(settings)

# Explicit imports — autodiscover only loads app.tasks.__init__ (no tasks.py).
import app.tasks.ai  # noqa: F401
import app.tasks.archive  # noqa: F401
import app.tasks.cluster  # noqa: F401
import app.tasks.fetch  # noqa: F401
import app.tasks.publish  # noqa: F401

# Celery CLI (-A app.tasks.celery_app) expects an `app` attribute.
app = celery_app


@worker_process_init.connect
def init_ml_model(**kwargs):
    try:
        from app.clustering.embedder import _get_model

        _get_model()
    except Exception:
        pass


@worker_ready.connect
def bootstrap_pipeline(sender, **kwargs):
    """On worker start: clear orphaned default Celery queue, purge backlog, kick fetch."""
    try:
        import redis

        client = redis.from_url(get_settings().REDIS_URL)
        # Beat enqueues to the built-in "celery" queue; worker listens on "default,ml".
        if client.llen("celery") > 0:
            client.delete("celery")
        if client.llen("default") > 20:
            sender.control.purge()
        # Orphan global fetch lock from the old monolithic task blocks all fetches.
        client.delete("task:fetch_all_sources")
        for sid in range(1, 64):
            client.delete(f"task:fetch_source:{sid}")
    except Exception:
        pass

    from app.tasks.cluster import dispatch_cluster
    from app.tasks.fetch import dispatch_fetch

    dispatch_fetch.apply_async(countdown=10)
    dispatch_cluster.apply_async(countdown=15)
