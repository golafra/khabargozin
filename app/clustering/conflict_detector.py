"""Source conflicts and critical numeric change detection."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clustering.feature_store import FeatureStore
from app.clustering.fingerprint import topics_are_incompatible
from app.clustering.text_normalize import normalize_persian_numerals
from app.db.models.message import Message

NUMERIC_PATTERNS: list[tuple[str, str]] = [
    (r"(\d+)\s*(کشته|فوتی|شهید|جان\s*باخت)", "casualty"),
    (r"(\d+)\s*(مصدوم|مجروح)", "injured"),
    (r"(\d+)\s*(مفقود)", "missing"),
    (r"(\d+(?:\.\d+)?)\s*(ریشتر|درجه)", "magnitude"),
    (r"(\d+(?:\.\d+)?)\s*(درصد|%)", "percent"),
    (r"(\d[\d,]*)\s*(میلیارد|میلیون|تومان|دلار|ریال)", "amount"),
]


@dataclass
class NumericDelta:
    kind: str
    old_value: str
    new_value: str


def extract_numeric_facts(text: str) -> dict[str, list[str]]:
    normalized = normalize_persian_numerals(text or "")
    facts: dict[str, list[str]] = {}
    for pattern, kind in NUMERIC_PATTERNS:
        for match in re.finditer(pattern, normalized):
            value = match.group(1).replace(",", "")
            facts.setdefault(kind, []).append(value)
    return facts


def detect_critical_numeric_changes(old_texts: list[str], new_text: str) -> list[NumericDelta]:
    combined_old = " ".join(old_texts)
    old_facts = extract_numeric_facts(combined_old)
    new_facts = extract_numeric_facts(new_text)
    deltas: list[NumericDelta] = []
    for kind in set(old_facts) | set(new_facts):
        old_vals = old_facts.get(kind, [])
        new_vals = new_facts.get(kind, [])
        if old_vals and new_vals and old_vals != new_vals:
            deltas.append(
                NumericDelta(
                    kind=kind,
                    old_value=",".join(old_vals),
                    new_value=",".join(new_vals),
                )
            )
    return deltas


def detect_source_conflict(session: Session, cluster_id: int) -> bool:
    messages = session.scalars(
        select(Message).where(Message.cluster_id == cluster_id, Message.is_deleted.is_(False))
    ).all()
    if len(messages) < 2:
        return False

    store = FeatureStore()
    topics: set[str] = set()
    for msg in messages:
        feats = store.read(msg)
        topics.add(feats.topic or feats.fingerprint.get("topic", "general"))

    topic_list = [t for t in topics if t != "general"]
    if len(topic_list) >= 2:
        for i, ta in enumerate(topic_list):
            for tb in topic_list[i + 1 :]:
                if topics_are_incompatible(ta, tb):
                    return True
    return False
