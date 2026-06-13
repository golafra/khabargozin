"""Telethon fetcher stub — swap backend when ICA is unavailable."""

from app.db.models.source import Source
from app.fetcher.base import FetchBatchResult, FetchCursor, FetcherBackend


class TelethonFetcher(FetcherBackend):
    """
    Placeholder for Telethon integration.
    Raises NotImplementedError — configure FETCHER_BACKEND=ica for production.
    """

    def fetch_messages(self, source: Source, cursor: FetchCursor) -> FetchBatchResult:
        raise NotImplementedError(
            f"TelethonFetcher not configured. Use ICA or implement Telethon for @{source.username}"
        )
