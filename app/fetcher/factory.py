"""Fetcher factory — tasks must use this, never ICA directly."""

from app.config import get_settings
from app.fetcher.base import FetchBatchResult, FetcherBackend
from app.fetcher.ica_client import ICAFetcher
from app.fetcher.telethon_client import TelethonFetcher


class MockFetcher(FetcherBackend):
    """In-memory fetcher for tests."""

    def __init__(self, messages_by_username: dict | None = None, backfill_complete: bool = True) -> None:
        self._messages = messages_by_username or {}
        self._backfill_complete = backfill_complete

    def fetch_messages(self, source, cursor) -> FetchBatchResult:
        msgs = list(self._messages.get(source.username, []))
        return FetchBatchResult(messages=msgs, backfill_complete=self._backfill_complete)

    def fetch_message_by_id(self, source, message_id: int):
        for msg in self._messages.get(source.username, []):
            if msg.message_id == message_id:
                return msg
        return None


def get_fetcher() -> FetcherBackend:
    backend = get_settings().FETCHER_BACKEND
    if backend == "mock":
        return MockFetcher()
    if backend == "telethon":
        return TelethonFetcher()
    return ICAFetcher()
