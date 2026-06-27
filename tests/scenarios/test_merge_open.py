"""Merge open clusters — hybrid similarity + reranker tests."""

from unittest.mock import MagicMock, patch

from app.clustering.merge import search_merge_target


def test_search_merge_target_with_rerank():
    session = MagicMock()
    message = MagicMock()
    message.text = "زلزله در فارس"
    message.id = 1
    message.published_at = None
    message.embedding = [0.1] * 1024

    features = MagicMock()
    features.news_type = "breaking"
    features.topic = "earthquake"

    hybrid_result = MagicMock(
        adjusted_score=0.9,
        score=0.9,
        should_merge=True,
        fingerprint_block=False,
        match_reason="hybrid",
        components={},
    )

    cluster = MagicMock()
    cluster.status = "scored"
    cluster.anchor_message_id = 2
    anchor = MagicMock(text="زلزله شدید در فارس", id=2, embedding=[0.1] * 1024)

    with patch("app.clustering.merge.find_similar_clusters", return_value=[(42, 0.85)]):
        with patch("app.clustering.merge.ann_top_k", return_value=20):
            with patch("app.clustering.merge.hybrid_similarity", return_value=hybrid_result):
                with patch("app.clustering.merge.rerank_candidates", return_value=[(42, 0.8)]):
                    session.get.side_effect = lambda model, pk: cluster if pk == 42 else anchor
                    session.scalars.return_value.first.return_value = anchor
                    result = search_merge_target(session, message, [0.1] * 1024, features=features)
    assert result.target_id == 42
