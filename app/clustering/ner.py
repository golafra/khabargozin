"""Typed NER — Hazm when available."""

from __future__ import annotations

from typing import Dict, List

_HAZM_TAG_MAP = {
    "PERSON": "PERSON",
    "PER": "PERSON",
    "LOCATION": "LOCATION",
    "LOC": "LOCATION",
    "ORGANIZATION": "ORGANIZATION",
    "ORG": "ORGANIZATION",
    "GPE": "LOCATION",
    "FAC": "LOCATION",
}


def extract_entities_typed(text: str) -> Dict[str, List[str]]:
    try:
        from hazm import NerTagger, word_tokenize

        tagger = _get_tagger()
        tokens = word_tokenize(text)
        tags = tagger.tag(tokens)
        result: Dict[str, List[str]] = {"PERSON": [], "LOCATION": [], "ORGANIZATION": []}
        for token, tag in tags:
            if len(token) <= 1 or tag == "O":
                continue
            bucket = _HAZM_TAG_MAP.get(tag)
            if bucket and token not in result[bucket]:
                result[bucket].append(token)
        return result
    except Exception:
        return {"PERSON": [], "LOCATION": [], "ORGANIZATION": []}


_tagger_instance = None


def _get_tagger():
    global _tagger_instance
    if _tagger_instance is None:
        from hazm import NerTagger

        _tagger_instance = NerTagger(model="resources/ner/peyma-ner")
    return _tagger_instance


def extract_entities(text: str) -> set[str]:
    typed = extract_entities_typed(text)
    out: set[str] = set()
    for values in typed.values():
        out.update(values)
    return out


def ner_overlap(text_a: str, text_b: str) -> float:
    entities_a = extract_entities(text_a)
    entities_b = extract_entities(text_b)
    if not entities_a or not entities_b:
        return 0.0
    intersection = entities_a & entities_b
    union = entities_a | entities_b
    return len(intersection) / len(union)
