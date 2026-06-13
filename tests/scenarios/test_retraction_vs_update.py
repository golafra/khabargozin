"""Retraction vs update routing."""

from app.publisher.retraction_state import RetractionState
from app.ai.schemas import RetractionClassifyOutput


def test_classify_update_not_retraction():
    result = RetractionClassifyOutput(type="update", confidence=0.85, corrected_text="جزئیات جدید")
    assert result.type == "update"
    state = RetractionState.UPDATE if result.type == "update" else RetractionState.RETRACTION
    assert state == RetractionState.UPDATE
