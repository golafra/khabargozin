"""Critical numeric change detection."""

from app.clustering.conflict_detector import detect_critical_numeric_changes, extract_numeric_facts
from app.clustering.text_normalize import normalize_persian_numerals


def test_persian_word_number_normalization():
    assert "12" in normalize_persian_numerals("دوازده کشته")
    assert "12" in normalize_persian_numerals("۱۲ مصدوم")


def test_digit_casualty_extracted():
    facts = extract_numeric_facts("12 مصدوم")
    assert "injured" in facts


def test_casualty_delta_detected():
    old = ["۱۰ کشته در زلزله"]
    new = "۱۲ کشته در زلزله"
    deltas = detect_critical_numeric_changes(old, new)
    assert len(deltas) >= 1
    assert deltas[0].kind == "casualty"
