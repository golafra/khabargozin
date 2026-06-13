"""Fetcher pagination and backfill tests."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.fetcher.base import FetchBatchResult, FetchCursor, RawMessage
from app.fetcher.factory import MockFetcher


def test_mock_fetcher_backfill_incomplete():
    now = datetime.now(timezone.utc)
    msgs = [RawMessage(message_id=i, text=f"msg {i}", published_at=now) for i in range(3)]
    fetcher = MockFetcher({"TestChannel": msgs}, backfill_complete=False)
    source = MagicMock(username="TestChannel")
    result = fetcher.fetch_messages(source, FetchCursor())
    assert len(result.messages) == 3
    assert result.backfill_complete is False


def test_mock_fetcher_backfill_complete():
    now = datetime.now(timezone.utc)
    msgs = [RawMessage(message_id=1, text="ok", published_at=now)]
    fetcher = MockFetcher({"Ch": msgs}, backfill_complete=True)
    source = MagicMock(username="Ch")
    result = fetcher.fetch_messages(source, FetchCursor())
    assert result.backfill_complete is True
