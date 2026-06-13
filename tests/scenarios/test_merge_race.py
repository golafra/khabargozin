"""Merge race — FOR UPDATE lock required."""

import pytest

from app.resilience.locking import assert_no_slow_ops, mark_slow_op


def test_slow_op_forbidden_inside_lock():
    mark_slow_op(True)
    with pytest.raises(AssertionError, match="FORBIDDEN"):
        assert_no_slow_ops()
    mark_slow_op(False)
    assert_no_slow_ops()  # should not raise
