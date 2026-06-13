"""AI JSON parser."""

import pytest

from app.ai.parser import parse_cluster_output


def test_parse_valid_json():
    raw = """{
        "status": "publish",
        "editorial_priority": 3,
        "confidence": 0.8,
        "headline": "تیتر خبر",
        "summary": "خلاصه",
        "why_it_matters": "مهم است",
        "conflicts": [],
        "sources_used": ["تسنیم"],
        "rejection_reason": "",
        "sensitivity": "normal",
        "needs_human_review": false
    }"""
    result = parse_cluster_output(raw)
    assert result.status == "publish"
    assert result.headline == "تیتر خبر"


def test_reject_html_in_headline():
    raw = """{
        "status": "publish",
        "editorial_priority": 3,
        "confidence": 0.8,
        "headline": "<b>bad</b>",
        "summary": "ok",
        "why_it_matters": "",
        "conflicts": [],
        "sources_used": [],
        "rejection_reason": "",
        "sensitivity": "normal",
        "needs_human_review": false
    }"""
    with pytest.raises(Exception):
        parse_cluster_output(raw)
