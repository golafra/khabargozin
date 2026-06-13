"""Fetcher backend abstraction."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol

from app.db.models.source import Source


@dataclass
class FetchCursor:
    last_message_id: Optional[int] = None
    overlap_start: Optional[datetime] = None


@dataclass
class RawMessage:
    message_id: int
    text: Optional[str]
    published_at: datetime
    edit_date: Optional[datetime] = None
    reply_to_message_id: Optional[int] = None
    url: Optional[str] = None
    media_meta: Optional[dict[str, Any]] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    has_text: bool = True
    message_type: str = "text"


@dataclass
class FetchBatchResult:
    messages: list[RawMessage]
    backfill_complete: bool = True


class FetcherBackend(Protocol):
    def fetch_messages(self, source: Source, cursor: FetchCursor) -> FetchBatchResult:
        """Fetch messages for a source within the cursor window."""
        ...
