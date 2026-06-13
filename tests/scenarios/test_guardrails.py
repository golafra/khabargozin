"""Sensitivity guardrails."""

from app.ai.guardrails import check_guardrails
from app.ai.schemas import AIClusterOutput


def test_sensitive_requires_two_sources():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=3,
        confidence=0.90,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="security",
    )
    ok, reason = check_guardrails(result, independent_source_count=1)
    assert ok is False
    assert reason == "sensitivity_guardrail_fail"


def test_sensitive_passes_with_two_sources():
    result = AIClusterOutput(
        status="publish",
        editorial_priority=3,
        confidence=0.90,
        headline="تیتر",
        summary="خلاصه",
        why_it_matters="",
        sensitivity="security",
    )
    ok, _ = check_guardrails(result, independent_source_count=2)
    assert ok is True
