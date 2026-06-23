"""Normalize Telegram text for clustering similarity."""

import re

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FEFF"
    "🔺🔹🔸🔻▫️💢📊🔴▪️•"
    "]+",
    flags=re.UNICODE,
)


def normalize_for_clustering(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    cleaned = _EMOJI_RE.sub(" ", text)
    cleaned = re.sub(r"[@#]\S+", " ", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
