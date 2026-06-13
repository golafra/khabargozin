"""Hold expire — phase 2."""

from datetime import datetime, timedelta, timezone

from app.publisher.hold import should_hold
from app.config import Settings


def test_hold_expires_with_single_source():
    settings = Settings(HOLD_MIN_SOURCES=2, HOLD_CONFIDENCE_THRESHOLD=0.70)
    # priority 4+, single source → hold
    assert should_hold(4, 1, 0.65, False) is True
