"""Review feedback reject reason validation."""

import pytest
from unittest.mock import MagicMock

from app.admin.review import ReviewValidationError, submit_review, validate_review


def test_reject_without_reason_raises():
    with pytest.raises(ReviewValidationError):
        validate_review("reject_publish", None)


def test_reject_with_reason_ok():
    session = MagicMock()
    session.get.return_value = MagicMock()
    session.scalars.return_value.all.return_value = []
    row = submit_review(session, 1, "reject_publish", reject_reason="topic_mismatch")
    assert row.action == "reject_publish"
