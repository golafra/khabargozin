"""AI parser fallback for title/content responses."""

from app.ai.parser import parse_cluster_output


def test_parse_title_content_fallback():
    raw = """{
  "title": "تحولات جدید در بازار ارز",
  "content": "بازار با نوسانات شدید مواجه است"
}"""
    result = parse_cluster_output(raw)
    assert result.headline == "تحولات جدید در بازار ارز"
    assert result.summary == "بازار با نوسانات شدید مواجه است"
    assert result.status in ("publish", "reject")
