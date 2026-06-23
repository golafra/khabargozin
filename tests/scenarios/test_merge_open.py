"""Merge open clusters — two similar messages → one cluster."""

from unittest.mock import MagicMock, patch

from app.clustering.merge import find_merge_target


def test_find_merge_target_high_similarity():
    session = MagicMock()
    message = MagicMock()
    message.text = "زلزله در فارس"
    message.id = 1

    with patch("app.clustering.merge.find_similar_clusters", return_value=[(42, 0.85)]):
        with patch("app.clustering.merge.ner_overlap", return_value=0.0):
            cluster = MagicMock()
            cluster.status = "scored"
            session.get.return_value = cluster
            sample = MagicMock(text="زلزله شدید در فارس")
            session.query.return_value.filter_by.return_value.first.return_value = sample
            target = find_merge_target(session, message, [0.1] * 384)
    assert target == 42
