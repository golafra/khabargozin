"""HTML formatter with escape."""

import html

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import AIClusterOutput
from app.db.models.message import Message
from app.db.models.source import Source


def telegram_post_url(username: str, message_id: int) -> str:
    """Public t.me link to the exact channel post."""
    handle = (username or "").strip().lstrip("@")
    return f"https://t.me/{handle}/{message_id}"


def format_publication_html(
    session: Session,
    cluster_id: int,
    ai_result: AIClusterOutput,
) -> str:
    headline = html.escape(ai_result.headline)
    summary = html.escape(ai_result.summary)
    parts = [f"<b>{headline}</b>", "", summary]

    if ai_result.why_it_matters:
        parts.extend(["", html.escape(ai_result.why_it_matters)])

    if ai_result.conflicts:
        parts.append("")
        parts.append("<b>اختلاف روایت:</b>")
        for conflict in ai_result.conflicts:
            parts.append(f"• {html.escape(str(conflict))}")

    attributions = _build_attributions(session, cluster_id)
    if attributions:
        parts.extend(["", "<i>منابع:</i> " + " | ".join(attributions)])

    return "\n".join(parts)


def _source_link_label(src: Source) -> str:
    """Persian channel name only — no @username or numeric ids in visible text."""
    label = (src.display_name or "").strip()
    if label:
        return html.escape(label)
    handle = (src.username or "").strip().lstrip("@")
    return html.escape(handle or "منبع")


def _build_attributions(session: Session, cluster_id: int) -> list[str]:
    rows = session.execute(
        select(Message, Source)
        .join(Source, Message.source_id == Source.id)
        .where(Message.cluster_id == cluster_id)
        .order_by(Source.credibility_weight.desc(), Message.published_at.asc())
    ).all()

    seen: set[int] = set()
    links: list[str] = []
    for msg, src in rows:
        if src.id in seen:
            continue
        seen.add(src.id)
        label = _source_link_label(src)
        if msg.is_deleted:
            links.append(f"[حذف‌شده] {label}")
        else:
            post_url = telegram_post_url(src.username, int(msg.message_id))
            links.append(f'<a href="{html.escape(post_url, quote=True)}">{label}</a>')
    return links
