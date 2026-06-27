"""Tests for publication formatter and AI style polish."""

from unittest.mock import MagicMock

from app.ai.parser import normalize_cluster_data
from app.ai.style import dedupe_headline_from_summary, polish_cluster_text, polish_prose
from app.publisher.formatter import telegram_post_url, _build_attributions


def test_telegram_post_url():
    assert telegram_post_url("Tasnimnews", 12345) == "https://t.me/Tasnimnews/12345"
    assert telegram_post_url("@mehrnews", 99) == "https://t.me/mehrnews/99"


def test_build_attributions_links_to_exact_post():
    session = MagicMock()
    msg = MagicMock()
    msg.message_id = 555
    msg.is_deleted = False
    src = MagicMock()
    src.id = 1
    src.username = "Tasnimnews"
    src.display_name = "تسنیم"
    session.execute.return_value.all.return_value = [(msg, src)]

    links = _build_attributions(session, cluster_id=10)
    assert len(links) == 1
    assert 'href="https://t.me/Tasnimnews/555"' in links[0]
    assert links[0].endswith(">تسنیم</a>")
    assert "(@" not in links[0]


def test_dedupe_headline_from_summary():
    headline = "سخنگوی وزارت خارجه ایران: هیچ محدودیتی در تصمیم‌گیری درباره اموال آزادشده وجود ندارد"
    summary = (
        "سخنگوی وزارت امور خارجه ایران در اظهارات اخیر خود به موضوع اموال آزادشده اشاره کرد."
    )
    cleaned = polish_cluster_text(headline, summary)[1]
    assert "اشاره کرد" not in cleaned
    assert "در اظهارات" not in cleaned


def test_normalize_applies_polish():
    data = normalize_cluster_data(
        {
            "headline": "افزایش قیمت دلار",
            "summary": "افزایش قیمت دلار در بازار اشاره کرد که نرخ بالا رفته است.",
            "status": "publish",
            "editorial_priority": 3,
            "confidence": 0.8,
        }
    )
    assert data["summary"].startswith("افزایش قیمت دلار") is False or "اشاره کرد" not in data["summary"]
