"""Normalize Telegram text for clustering similarity."""

import re

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FEFF"
    "🔺🔹🔸🔻▫️💢📊🔴▪️•"
    "]+",
    flags=re.UNICODE,
)


def normalize_for_clustering(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    cleaned = _EMOJI_RE.sub(" ", text)
    cleaned = re.sub(r"[@#]\S+", " ", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_WORD_ONES = {
    "صفر": 0, "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15,
    "شانزده": 16, "هفده": 17, "هجده": 18, "نوزده": 19,
}
_WORD_TENS = {
    "بیست": 20, "سی": 30, "چهل": 40, "پنجاه": 50,
    "شصت": 60, "هفتاد": 70, "هشتاد": 80, "نود": 90,
}
_WORD_SCALES = {
    "صد": 100, "هزار": 1000, "میلیون": 1_000_000, "میلیارد": 1_000_000_000,
}


def _parse_persian_number_phrase(phrase: str) -> int | None:
    phrase = phrase.strip().replace(" و ", " ")
    tokens = phrase.split()
    if not tokens:
        return None
    total = 0
    current = 0
    for tok in tokens:
        if tok in _WORD_ONES:
            current += _WORD_ONES[tok]
        elif tok in _WORD_TENS:
            current += _WORD_TENS[tok]
        elif tok in _WORD_SCALES:
            scale = _WORD_SCALES[tok]
            if current == 0:
                current = 1
            total += current * scale
            current = 0
        else:
            return None
    return total + current


_MULTI_WORD_NUMBERS: list[tuple[str, str]] = [
    ("پنجاه و سه", "53"),
    ("پنجاه و ۳", "53"),
    ("دوازده", "12"),
    ("یازده", "11"),
]


def normalize_persian_numerals(text: str) -> str:
    """Convert Persian digits and common word-numbers to Arabic numerals."""
    if not text:
        return ""
    out = text.translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)

    for phrase, num in sorted(_MULTI_WORD_NUMBERS, key=lambda x: -len(x[0])):
        out = out.replace(phrase, num)

    def _replace_word_number(match: re.Match) -> str:
        val = _parse_persian_number_phrase(match.group(0))
        return str(val) if val is not None else match.group(0)

    word_pattern = (
        r"\b((?:صفر|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|یازده|دوازده|سیزده|چهارده|پانزده|"
        r"شانزده|هفده|هجده|نوزده|بیست|سی|چهل|پنجاه|شصت|هفتاد|هشتاد|نود|صد|هزار|میلیون|میلیارد)"
        r"(?:\s+و\s+(?:صفر|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|یازده|دوازده|سیزده|چهارده|پانزده|"
        r"شانزده|هفده|هجده|نوزده|بیست|سی|چهل|پنجاه|شصت|هفتاد|هشتاد|نود|صد|هزار|میلیون|میلیارد))*)\b"
    )
    out = re.sub(word_pattern, _replace_word_number, out)
    return out
