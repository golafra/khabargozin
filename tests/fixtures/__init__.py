"""Shared test fixtures."""

from datetime import datetime, timezone

SAMPLE_TEXT_A = "زلزله ۵.۲ ریشتری در استان فارس ثبت شد"
SAMPLE_TEXT_B = "زلزله ۵.۲ ریشتری در استان فارس گزارش شد"
SAMPLE_TEXT_REPOST = SAMPLE_TEXT_A

NOW = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)


def sample_raw_message(message_id: int = 1, text: str = SAMPLE_TEXT_A):
    from app.fetcher.base import RawMessage

    return RawMessage(
        message_id=message_id,
        text=text,
        published_at=NOW,
        has_text=True,
    )
