"""Fingerprint soft penalty tests."""

from app.clustering.fingerprint import fingerprint_compatibility


def test_tabriz_azerbaijan_soft_not_block():
    fp_a = {"topic": "earthquake", "topic_confidence": 0.9, "locations": ["تبریز"], "persons": [], "organizations": []}
    fp_b = {"topic": "earthquake", "topic_confidence": 0.9, "locations": ["آذربایجان شرقی"], "persons": [], "organizations": []}
    result = fingerprint_compatibility(fp_a, fp_b)
    assert result.block is False
    assert result.penalty >= 0


def test_earthquake_vs_bourse_hard_block():
    fp_a = {"topic": "earthquake", "topic_confidence": 0.92, "locations": [], "persons": [], "organizations": []}
    fp_b = {"topic": "economic", "topic_confidence": 0.9, "locations": [], "persons": [], "organizations": []}
    result = fingerprint_compatibility(fp_a, fp_b)
    assert result.block is True


def test_bourse_metaphor_soft_penalty():
    fp_a = {"topic": "earthquake", "topic_confidence": 0.5, "locations": [], "persons": [], "organizations": []}
    fp_b = {"topic": "economic", "topic_confidence": 0.55, "locations": [], "persons": [], "organizations": []}
    result = fingerprint_compatibility(fp_a, fp_b)
    assert result.block is False
    assert result.penalty >= 0.5
