"""Mock fetcher backend injection."""

from datetime import datetime, timezone

from app.fetcher.base import FetchBatchResult, RawMessage
from app.fetcher.factory import MockFetcher, get_fetcher


def test_mock_fetcher_returns_injected_messages():
    now = datetime.now(timezone.utc)
    raw = RawMessage(message_id=1, text="test", published_at=now)

    class FakeSource:
        username = "TestChannel"

    fetcher = MockFetcher({"TestChannel": [raw]})
    result = fetcher.fetch_messages(FakeSource(), None)  # type: ignore
    assert len(result.messages) == 1
    assert result.backfill_complete is True


def test_get_fetcher_mock_mode(monkeypatch):
    monkeypatch.setenv("FETCHER_BACKEND", "mock")
    from app.config import get_settings
    get_settings.cache_clear()
    fetcher = get_fetcher()
    assert isinstance(fetcher, MockFetcher)
    get_settings.cache_clear()
