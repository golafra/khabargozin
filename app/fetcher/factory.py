"""Fetcher factory — tasks must use this, never ICA directly."""

from app.config import get_settings
from app.fetcher.base import FetcherBackend
from app.fetcher.ica_client import ICAFetcher


class MockFetcher(FetcherBackend):
    """In-memory fetcher for tests."""

    def __init__(self, messages_by_username: dict | None = None) -> None:
        self._messages = messages_by_username or {}

    def fetch_messages(self, source, cursor):
        return list(self._messages.get(source.username, []))


def get_fetcher() -> FetcherBackend:
    backend = get_settings().FETCHER_BACKEND
    if backend == "mock":
        return MockFetcher()
    return ICAFetcher()
