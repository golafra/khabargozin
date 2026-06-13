"""Media filtering — MVP + phase 2 preview checks."""

from typing import Any, Optional

import httpx

from app.config import get_settings

ICA_MEDIA_BASE = "https://tg.i-c-a.su/media"


def extract_media_meta(media: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not media:
        return None
    media_type = media.get("_", "")
    meta: dict[str, Any] = {"raw_type": media_type}

    if media_type == "messageMediaPhoto":
        photo = media.get("photo") or {}
        sizes = photo.get("sizes") or []
        best = _best_photo_size(sizes)
        if best:
            meta.update({"type": "photo", "width": best.get("w"), "height": best.get("h")})
        else:
            meta["type"] = "photo"
        return meta

    if media_type == "messageMediaDocument":
        doc = media.get("document") or {}
        meta["mime_type"] = doc.get("mime_type")
        for attr in doc.get("attributes") or []:
            if attr.get("_") == "documentAttributeVideo":
                meta.update({
                    "type": "video",
                    "duration": attr.get("duration"),
                    "width": attr.get("w"),
                    "height": attr.get("h"),
                })
                return meta
            if attr.get("_") == "documentAttributeImageSize":
                meta.update({
                    "type": "image",
                    "width": attr.get("w"),
                    "height": attr.get("h"),
                })
                return meta
        meta["type"] = "document"
        return meta

    return None


def _best_photo_size(sizes: list[dict]) -> Optional[dict]:
    candidates = [s for s in sizes if "w" in s and "h" in s]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.get("w", 0) or 0) * (s.get("h", 0) or 0))


def fetch_preview_size(channel: str, message_id: int) -> Optional[int]:
    """HEAD request to ICA preview endpoint — returns Content-Length if available."""
    settings = get_settings()
    if not settings.MEDIA_PREVIEW_ENABLED:
        return None
    url = f"{ICA_MEDIA_BASE}/{channel}/{message_id}/preview"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.head(url)
            if resp.status_code == 200:
                return int(resp.headers.get("content-length", 0) or 0)
    except Exception:
        return None
    return None


def is_media_acceptable(
    media_meta: dict[str, Any],
    *,
    channel: Optional[str] = None,
    message_id: Optional[int] = None,
) -> bool:
    settings = get_settings()
    width = media_meta.get("width")
    height = media_meta.get("height")
    if width and height and height > 0:
        ratio = width / height
        if ratio < settings.MEDIA_MIN_ASPECT_RATIO or ratio > settings.MEDIA_MAX_ASPECT_RATIO:
            return False
    if media_meta.get("type") == "video":
        duration = media_meta.get("duration") or 0
        if duration > settings.MEDIA_MAX_VIDEO_SECONDS:
            return False
    if channel and message_id and media_meta.get("type") == "photo":
        preview_size = fetch_preview_size(channel, message_id)
        if preview_size is not None and 0 < preview_size < settings.MEDIA_MIN_PREVIEW_BYTES:
            return False
    return True


def select_first_valid_media(messages_media: list[Optional[dict]]) -> Optional[dict]:
    for media in messages_media:
        if media and is_media_acceptable(media):
            return media
    return None
