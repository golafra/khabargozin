"""Archive Celery task."""

from app.tasks.archive import archive_old_data
from app.tasks.celery_app import app


@app.task(name="app.tasks.archive.archive_old_records", acks_late=True)
def archive_old_records() -> dict:
    from app.db.session import get_session

    session = get_session()
    try:
        counts = archive_old_data(session)
        session.commit()
        return counts
    finally:
        session.close()
