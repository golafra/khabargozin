"""ICA API client — implements FetcherBackend."""

from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import redis

from app.config import get_settings
from app.db.models.source import Source
from app.fetcher.base import FetchBatchResult, FetchCursor, FetcherBackend, RawMessage
from app.fetcher.media_filter import extract_media_meta, is_media_acceptable


class ICAFetcher(FetcherBackend):
    BASE_URL = "https://tg.i-c-a.su/json"

    def __init__(self, client: Optional[httpx.Client] = None) -> None:
        self._client = client or httpx.Client(timeout=30.0)
        self._settings = get_settings()

    def _throttle(self) -> None:
        """Global Redis gate — one ICA request at a time across all workers."""
        min_interval = max(self._settings.ica_min_interval_seconds, 10.0)
        client = redis.from_url(self._settings.REDIS_URL)
        while not client.set("ica:global_gate", "1", nx=True, ex=int(min_interval)):
            time.sleep(0.25)

    def _get_page(self, url: str, retries: int = 5) -> dict:
        last_response = None
        for attempt in range(retries):
            self._throttle()
            last_response = self._client.get(url)
            if last_response.status_code == 429:
                wait = max(self._settings.TELEGRAM_FLOODWAIT_DEFAULT_SECONDS, 30.0)
                match = re.search(r"FLOOD_WAIT_(\d+)", last_response.text)
                if match:
                    wait = float(match.group(1)) + 1
                time.sleep(wait)
                continue
            last_response.raise_for_status()
            return last_response.json()
        if last_response is not None and last_response.status_code == 429:
            time.sleep(45)
            self._throttle()
            last_response = self._client.get(url)
            last_response.raise_for_status()
            return last_response.json()
        if last_response is not None:
            last_response.raise_for_status()
        raise httpx.HTTPError(f"ICA request failed after {retries} retries: {url}")

    def fetch_messages(self, source: Source, cursor: FetchCursor) -> FetchBatchResult:
        collected: list[RawMessage] = []
        overlap_start = cursor.overlap_start
        page = 1
        reached_overlap = False

        while page <= self._settings.FETCH_MAX_PAGES:
            url = (
                f"{self.BASE_URL}/{source.username}"
                f"?limit={self._settings.FETCH_PAGE_SIZE}&page={page}"
            )
            payload = self._get_page(url)
            messages = payload.get("messages") or []
            if not messages:
                break

            for raw in messages:
                parsed = self._parse_message(raw, source.username)
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

        backfill_complete = reached_overlap or page < self._settings.FETCH_MAX_PAGES
        return FetchBatchResult(messages=collected, backfill_complete=backfill_complete)

    def fetch_message_by_id(self, source: Source, message_id: int) -> Optional[RawMessage]:
        """Re-fetch a single message for edit_date updates."""
        url = f"{self.BASE_URL}/{source.username}/{message_id}"
        try:
            payload = self._get_page(url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 400):
                return None
            raise
        if not isinstance(payload, dict) or "id" not in payload:
            return None
        return self._parse_message(payload, source.username)

    def _parse_message(self, raw: dict[str, Any], channel: str) -> RawMessage:
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
            if not is_media_acceptable(
                media_meta, channel=channel, message_id=raw["id"]
            ):
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
