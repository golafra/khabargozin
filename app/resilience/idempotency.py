"""Idempotency helpers."""

import hashlib


def message_dedupe_key(source_id: int, message_id: int) -> str:
    return f"{source_id}:{message_id}"


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()
