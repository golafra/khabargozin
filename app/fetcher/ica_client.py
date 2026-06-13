"""ICA API client — implements FetcherBackend."""

from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.db.models.source import Source
from app.fetcher.base import FetchCursor, FetcherBackend, RawMessage
from app.fetcher.media_filter import extract_media_meta, is_media_acceptable


class ICAFetcher(FetcherBackend):
    BASE_URL = "https://tg.i-c-a.su/json"

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)
        self._settings = get_settings()
        self._last_request_at: float = 0.0

    def _throttle(self) -> None:
        min_interval = self._settings.ica_min_interval_seconds
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def fetch_messages(self, source: Source, cursor: FetchCursor) -> list[RawMessage]:
        collected: list[RawMessage] = []
        overlap_start = cursor.overlap_start
        page = 1
        reached_overlap = False

        while page <= self._settings.FETCH_MAX_PAGES:
            self._throttle()
            url = (
                f"{self.BASE_URL}/{source.username}"
                f"?limit={self._settings.FETCH_PAGE_SIZE}&page={page}"
            )
            response = self._client.get(url)
            response.raise_for_status()
            payload = response.json()
            messages = payload.get("messages") or []
            if not messages:
                break

            for raw in messages:
                parsed = self._parse_message(raw)
                if overlap_start and parsed.published_at < overlap_start:
                    reached_overlap = True
                    break
                if cursor.last_message_id and parsed.message_id < cursor.last_message_id - self._settings.FETCH_SLIDING_WINDOW:
                    if overlap_start and parsed.published_at < overlap_start:
                        reached_overlap = True
                        break
                collected.append(parsed)

            if reached_overlap:
                break
            page += 1
            if page <= self._settings.FETCH_MAX_PAGES:
                time.sleep(self._settings.FETCH_PAGINATION_DELAY_SECONDS)

        return collected

    def _parse_message(self, raw: dict[str, Any]) -> RawMessage:
        published_at = datetime.fromtimestamp(raw["date"], tz=timezone.utc)
        edit_date = None
        if raw.get("edit_date"):
            edit_date = datetime.fromtimestamp(raw["edit_date"], tz=timezone.utc)

        text = raw.get("message") or ""
        plain_text = self._strip_html(text)
        media_meta = extract_media_meta(raw.get("media"))
        message_type = "text"
        if media_meta:
            message_type = media_meta.get("type", "media")
            if not is_media_acceptable(media_meta):
                media_meta = None

        reply_to = raw.get("reply_to")
        reply_id = None
        if isinstance(reply_to, dict):
            reply_id = reply_to.get("reply_to_msg_id")

        url = self._extract_url(text)

        return RawMessage(
            message_id=raw["id"],
            text=plain_text or None,
            published_at=published_at,
            edit_date=edit_date,
            reply_to_message_id=reply_id,
            url=url,
            media_meta=media_meta,
            raw_payload=raw,
            has_text=bool(plain_text.strip()),
            message_type=message_type,
        )

    @staticmethod
    def _strip_html(text: str) -> str:
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return html.unescape(text).strip()

    @staticmethod
    def _extract_url(text: str) -> Optional[str]:
        match = re.search(r'href="([^"]+)"', text)
        if match:
            href = match.group(1)
            if not href.startswith("http"):
                href = f"https://{href}"
            return href
        for token in text.split():
            if token.startswith("http"):
                return token.rstrip(".,)")
        return None
