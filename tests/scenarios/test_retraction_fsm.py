"""Retraction FSM — detection and classification."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.publisher.retraction import detect_retraction_candidates
from app.publisher.retraction_state import RetractionState


def test_detect_via_reply_to():
    session = MagicMock()
    message = MagicMock()
    message.reply_to_message_id = 100
    message.source_id = 1
    message.message_id = 200
    message.edit_date = None
    message.text = "تکذیب خبر"
    message.cluster_id = None

    with patch(
        "app.publisher.retraction._published_cluster_for_message",
        return_value=42,
    ):
        candidates = detect_retraction_candidates(session, message)
    assert 42 in candidates


def test_retraction_state_enum():
    assert RetractionState.RETRACTION.value == "retraction"
