"""Post-process AI prose for Telegram — less repetition, less agency clichés."""

import re

_TRAILING_FILLER_RE = re.compile(
    r"\s+(?:اشاره|تأکید|تاکید|خاطرنشان|اظهار)\s+کرد(?:\s+که)?[\.؟!]*\s*$",
    re.IGNORECASE,
)

_LEADING_FILLER_RE = re.compile(
    r"^در\s+(?:اظهارات|گفتگو|مصاحبه|نشست)[^،.؟!]*[،.؟!]\s*",
    re.IGNORECASE,
)

_NAQLE_GHAR_RE = re.compile(
    r"^به\s+نقل\s+از\s+[^،.؟!]+[،.؟!]\s*",
    re.IGNORECASE,
)

_META_INTRO_RE = re.compile(
    r"^در\s+(?:اظهارات|گفتگو|مصاحبه|نشست)\s+.+?به\s+موضوع\s+",
    re.IGNORECASE,
)

_TOPIC_PREFIX_RE = re.compile(r"^به\s+موضوع\s+", re.IGNORECASE)

_SPEAKER_LEAD_RE = re.compile(
    r"^(?:سخنگوی|معاون|وزیر|رئیس|نماینده|سفیر|مقام|مسئول|مدیر)\s+[^:]{0,100}:\s*",
    re.IGNORECASE,
)


def _collapse_ws(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def dedupe_headline_from_summary(headline: str, summary: str) -> str:
    if not headline or not summary:
        return summary
    h = headline.strip().rstrip(".")
    s = summary.strip()
    if s.startswith(h):
        return s[len(h) :].lstrip(" .،:؛-–—")
    h_words = h.split()
    for n in range(min(12, len(h_words)), 4, -1):
        prefix = " ".join(h_words[:n])
        if s.startswith(prefix):
            return s[len(prefix) :].lstrip(" .،:؛-–—")
    if "سخنگو" in h and s.startswith("سخنگو"):
        s = re.sub(
            r"^سخنگو\S*\s+[^.؟!]{0,120}?(?:ایران|کشور)\s+",
            "",
            s,
            count=1,
            flags=re.IGNORECASE,
        ).lstrip()
    return s


def polish_prose(text: str, *, is_headline: bool = False) -> str:
    if not text:
        return text
    text = _LEADING_FILLER_RE.sub("", text)
    text = _NAQLE_GHAR_RE.sub("", text)
    if not is_headline:
        text = _SPEAKER_LEAD_RE.sub("", text)
    text = _TRAILING_FILLER_RE.sub("", text)
    text = re.sub(r"\s+([،.؛:!?])", r"\1", text)
    return _collapse_ws(text)


def _strip_meta_intro(text: str, headline: str) -> str:
    text = _META_INTRO_RE.sub("", text)
    text = _TOPIC_PREFIX_RE.sub("", text)
    text = text.strip(" .،:؛-–—")
    if text and headline and text in headline:
        return ""
    return text


def polish_cluster_text(headline: str, summary: str, why_it_matters: str = "") -> tuple[str, str, str]:
    raw_headline = headline
    summary = dedupe_headline_from_summary(raw_headline, polish_prose(summary))
    summary = _strip_meta_intro(summary, raw_headline)
    headline = polish_prose(headline, is_headline=True)
    why = polish_prose(why_it_matters) if why_it_matters else ""
    if why:
        why = dedupe_headline_from_summary(raw_headline, why)
        why = _strip_meta_intro(why, raw_headline)
    return headline, summary, why
