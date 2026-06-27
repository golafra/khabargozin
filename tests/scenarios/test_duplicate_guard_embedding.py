"""Regression: pgvector returns numpy arrays — truthiness checks must not crash publish."""

import numpy as np
from unittest.mock import MagicMock, patch

from app.publisher.duplicate_guard import find_publish_duplicate


def test_find_publish_duplicate_handles_numpy_centroid():
    session = MagicMock()
    session.scalar.return_value = None
    cluster = MagicMock()
    cluster.id = 10
    cluster.centroid_embedding = np.zeros(1024, dtype=np.float32)

    with patch(
        "app.publisher.duplicate_guard.find_recent_published_similar",
        return_value=[],
    ):
        with patch("app.publisher.duplicate_guard.get_anchor_message", return_value=None):
            assert find_publish_duplicate(session, cluster) is None
