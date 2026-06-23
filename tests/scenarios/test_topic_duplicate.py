"""Tests for topic overlap merge and duplicate publish guard."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.clustering.text_normalize import normalize_for_clustering
from app.clustering.topic_overlap import (
    should_block_duplicate_publish,
    should_merge_open,
    topic_overlap,
)


BOURSE_A = "🔺رشد بیش از ۸۸ هزار واحدی شاخص کل بورس \n\n🔹در جریان معاملات امروز شاخص کل بورس با افزایش ۸۸ هزار واحد"
BOURSE_B = "رشد ۸۸ هزار واحدی شاخص بورس\n\n📊 شاخص کل بورس با رشد ۸۸ هزار واحدی در پایان معاملات امروز به ۵ میلیون و ۱۶۰ هزار واحد رسید"


def test_topic_overlap_bourse_pair():
    overlap = topic_overlap(BOURSE_A, BOURSE_B)
    assert overlap >= 0.30


def test_should_merge_open_with_topic_boost():
    assert should_merge_open(0.56, BOURSE_A, BOURSE_B) is True


def test_should_block_duplicate_publish_headlines():
    h1 = "رشد شاخص کل بورس به بیش از ۵ میلیون و ۱۶۰ هزار واحد"
    h2 = "رشد ۸۸ هزار واحدی شاخص بورس در پایان معاملات امروز"
    assert should_block_duplicate_publish(0.72, h1, h2) is True


def test_normalize_strips_emoji():
    assert "🔺" not in normalize_for_clustering(BOURSE_A)


def test_merge_published_rejects_unrelated_low_sim():
    from app.clustering.merge_published import find_published_merge_target

    session = MagicMock()
    message = MagicMock()
    message.text = "گلزنی رونالدو در دقیقه نود"
    message.published_at = datetime.now(timezone.utc)

    with patch(
        "app.clustering.merge_published.find_recent_published_similar",
        return_value=[(5, 0.70)],
    ):
        cluster = MagicMock()
        cluster.status = "published"
        cluster.window_end = message.published_at
        cluster.event_signature = "abc"
        session.get.return_value = cluster
        sample = MagicMock(text="شکست تیم ملی والیبال در بازی دوستانه")
        session.query.return_value.filter_by.return_value.first.return_value = sample
        target = find_published_merge_target(session, message, [0.1] * 384)
    assert target is None
