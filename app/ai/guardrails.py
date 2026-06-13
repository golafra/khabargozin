"""Sensitivity guardrails."""

from app.ai.schemas import AIClusterOutput
from app.config import get_settings

SENSITIVE_TYPES = frozenset({"political", "security", "casualty", "medical"})


def check_guardrails(result: AIClusterOutput, independent_source_count: int) -> tuple[bool, str | None]:
    settings = get_settings()
    if result.sensitivity not in SENSITIVE_TYPES:
        return True, None
    if independent_source_count < 2:
        return False, "sensitivity_guardrail_fail"
    if result.confidence < settings.SENSITIVE_MIN_CONFIDENCE:
        return False, "sensitivity_guardrail_fail"
    return True, None
