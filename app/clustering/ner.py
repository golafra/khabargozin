"""Optional NER boost — Hazm when available."""

from typing import Set


def extract_entities(text: str) -> Set[str]:
    try:
        from hazm import NerTagger, word_tokenize

        tagger = _get_tagger()
        tokens = word_tokenize(text)
        tags = tagger.tag(tokens)
        return {t[0] for t in tags if len(t) > 1 and t[1] != "O"}
    except Exception:
        return set()


_tagger_instance = None


def _get_tagger():
    global _tagger_instance
    if _tagger_instance is None:
        from hazm import NerTagger

        _tagger_instance = NerTagger(model="resources/ner/peyma-ner")
    return _tagger_instance


def ner_overlap(text_a: str, text_b: str) -> float:
    entities_a = extract_entities(text_a)
    entities_b = extract_entities(text_b)
    if not entities_a or not entities_b:
        return 0.0
    intersection = entities_a & entities_b
    union = entities_a | entities_b
    return len(intersection) / len(union)
