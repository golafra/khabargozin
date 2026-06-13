"""Telethon fetcher stub."""

import pytest

from app.fetcher.telethon_client import TelethonFetcher
from app.fetcher.base import FetchCursor
from unittest.mock import MagicMock


def test_telethon_raises_not_implemented():
    fetcher = TelethonFetcher()
    source = MagicMock(username="test")
    with pytest.raises(NotImplementedError):
        fetcher.fetch_messages(source, FetchCursor())
