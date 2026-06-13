"""Celery application."""

from celery import Celery
from celery.signals import worker_process_init

from app.config import get_settings

settings = get_settings()

app = Celery("khabargozin", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=settings.CELERY_MAX_TASKS_PER_CHILD,
    task_routes={
        "app.tasks.cluster.cluster_pending_messages": {"queue": "ml"},
    },
)


def build_schedule_from_settings(s: "Settings") -> dict:
    return {
        "fetch-all": {
            "task": "app.tasks.fetch.fetch_all_sources",
            "schedule": s.BEAT_FETCH_INTERVAL_SECONDS,
        },
        "cluster-pending": {
            "task": "app.tasks.cluster.cluster_pending_messages",
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


app.conf.beat_schedule = build_schedule_from_settings(settings)

app.autodiscover_tasks(["app.tasks"])


@worker_process_init.connect
def init_ml_model(**kwargs):
    try:
        from app.clustering.embedder import _get_model

        _get_model()
    except Exception:
        pass
