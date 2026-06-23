"""Shared helpers for admin UI."""

from datetime import datetime

ACTION_LABELS_FA = {
    "merged_into_cluster": "ادغام با خوشه باز (pgvector)",
    "merged_into_published": "الحاق به خبر منتشرشده",
    "new_cluster": "خوشه جدید — بدون ادغام",
    "message_edited": "ویرایش در منبع",
    "message_fetched": "خوانده‌شده از ICA",
    "threshold_passed": "عبور از آستانه امتیاز",
    "below_threshold": "رد — زیر آستانه",
    "ai_failed": "خطای AI",
    "pending_cluster": "در صف خوشه‌بندی",
    "clustered": "خوشه‌بندی شد",
    "duplicate_publish_blocked": "مسدود — تکرار انتشار",
}

MATCH_REASON_FA = {
    "similarity": "شباهت برداری ≥ 0.72",
    "similarity_ner": "شباهت + تقویت NER",
    "similarity_topic": "هم‌پوشانی موضوعی (بورس، شاخص، …)",
}


def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def message_times(msg) -> dict:
    return {
        "telegram_published": msg.published_at.isoformat() if msg.published_at else None,
        "telegram_published_fmt": fmt_dt(msg.published_at),
        "fetched_at": msg.created_at.isoformat() if msg.created_at else None,
        "fetched_fmt": fmt_dt(msg.created_at),
        "telegram_edited": msg.edit_date.isoformat() if msg.edit_date else None,
        "telegram_edited_fmt": fmt_dt(msg.edit_date) if msg.edit_date else None,
        "has_edit": bool(msg.edit_date),
    }


def action_label_fa(action: str | None) -> str:
    if not action:
        return "—"
    return ACTION_LABELS_FA.get(action, action)
