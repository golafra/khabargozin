"""HTML formatter with escape."""

import html
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import AIClusterOutput
from app.db.models.message import Message
from app.db.models.source import Source


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
        name = html.escape(src.display_name or src.username)
        if msg.is_deleted:
            links.append(f"[منبع حذف شد] {name}")
        elif msg.url:
            url = html.escape(msg.url, quote=True)
            links.append(f'<a href="{url}">{name}</a>')
        else:
            links.append(name)
    return links
