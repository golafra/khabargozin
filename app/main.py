"""Application entrypoint — healthcheck."""

import sys

from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine


def healthcheck() -> int:
    settings = get_settings()
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"khabargozin ok — publish_mode={settings.PUBLISH_MODE}")
        return 0
    except Exception as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(healthcheck())
