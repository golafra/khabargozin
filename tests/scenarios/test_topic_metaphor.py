"""News type classification — metaphor guard."""

from app.clustering.news_type import classify_news


def test_bourse_earthquake_metaphor_classified_economic():
    result = classify_news("زلزله در بازار بورس امروز")
    assert result.topic == "economic" or result.news_type == "economic"
    assert result.topic_confidence < 0.85
