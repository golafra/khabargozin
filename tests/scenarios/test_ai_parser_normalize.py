"""Tests for AI parser normalization."""

import pytest

from app.ai.parser import normalize_cluster_data, parse_cluster_output


def test_normalize_title_content():
    data = normalize_cluster_data({
        "title": "تیتر خبر",
        "content": "متن خلاصه",
        "confidence": 0.8,
        "editorial_priority": 4,
        "status": "publish",
    })
    assert data["headline"] == "تیتر خبر"
    assert data["summary"] == "متن خلاصه"


def test_normalize_claims_to_conflicts():
    data = normalize_cluster_data({
        "headline": "تیتر",
        "summary": "خلاصه",
        "claims": [{"claim": "ادعای اول"}, "ادعای دوم"],
        "status": "publish",
        "editorial_priority": 3,
        "confidence": 0.7,
    })
    assert len(data["conflicts"]) == 2


def test_parse_alternative_schema():
    raw = """{
        "title": "افزایش قیمت بنزین",
        "content": "قیمت بنزین در چند استان افزایش یافت.",
        "status": "publish",
        "editorial_priority": 3,
        "confidence": 0.85,
        "sensitivity": "normal",
        "needs_human_review": false
    }"""
    result = parse_cluster_output(raw)
    assert result.headline == "افزایش قیمت بنزین"
    assert result.confidence == 0.85
