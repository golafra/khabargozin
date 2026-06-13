"""Event signature — supplementary signal for merge."""

import hashlib
import re


def build_event_signature(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    tokens = re.findall(r"[\w\u0600-\u06FF]{3,}", normalized)
    key_tokens = sorted(set(tokens))[:20]
    raw = "|".join(key_tokens)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def event_signature_overlap(sig_a: str | None, sig_b: str | None) -> float:
    if not sig_a or not sig_b:
        return 0.0
    return 1.0 if sig_a == sig_b else 0.0
