"""pgvector search — mocked SQL path."""

from unittest.mock import MagicMock, patch

from app.clustering.vector_search import find_similar_clusters


def test_vector_search_returns_similarity():
    session = MagicMock()
    row = MagicMock()
    session.execute.return_value.fetchall.return_value = [(10, 0.88)]

    results = find_similar_clusters(session, [0.1] * 1024, limit=5)
    assert results == [(10, 0.88)]
    assert session.execute.call_count == 2
