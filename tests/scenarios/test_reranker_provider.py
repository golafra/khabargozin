"""Reranker provider offline mode."""

from app.clustering.reranker import OfflineReranker


def test_offline_reranker_scores_similar_text_higher():
    r = OfflineReranker()
    high = r.score("زلزله تبریز", "زلزله شدید در تبریز")
    low = r.score("زلزله تبریز", "نرخ دلار در بورس")
    assert high > low
