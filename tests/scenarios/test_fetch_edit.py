"""Edit_date re-check and upsert."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.fetcher.base import RawMessage
from app.tasks.fetch import _upsert_message


def test_upsert_updates_on_newer_edit_date():
    session = MagicMock()
    existing = MagicMock()
    existing.edit_date = datetime(2026, 6, 1, tzinfo=timezone.utc)
    session.scalar.return_value = existing

    raw = RawMessage(
        message_id=100,
        text="متن ویرایش‌شده",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        edit_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
    )
    source = MagicMock(id=1, username="TestCh")

    with patch("app.tasks.fetch.write_audit_log"):
        outcome = _upsert_message(session, source, raw)
    assert outcome == "updated"
    assert existing.text == "متن ویرایش‌شده"


def test_upsert_unchanged_without_edit():
    session = MagicMock()
    existing = MagicMock()
    existing.edit_date = datetime(2026, 6, 13, tzinfo=timezone.utc)
    session.scalar.return_value = existing

    raw = RawMessage(
        message_id=100,
        text="همان متن",
        published_at=datetime.now(timezone.utc),
        edit_date=None,
    )
    source = MagicMock(id=1, username="TestCh")
    assert _upsert_message(session, source, raw) == "unchanged"
