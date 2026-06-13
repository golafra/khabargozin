"""Telegram publish with FloodWait retry."""

import asyncio
import time
from typing import Any, Callable, Coroutine, TypeVar

from app.config import get_settings

T = TypeVar("T")

_last_send_at: float = 0.0


def _throttle() -> None:
    global _last_send_at
    settings = get_settings()
    elapsed = time.monotonic() - _last_send_at
    if elapsed < settings.TELEGRAM_PUBLISH_MIN_INTERVAL_SECONDS:
        time.sleep(settings.TELEGRAM_PUBLISH_MIN_INTERVAL_SECONDS - elapsed)
    _last_send_at = time.monotonic()


def publish_with_retry(send_fn: Callable[[], T]) -> T:
    """Sync wrapper around async telegram send with retry."""
    settings = get_settings()
    last_exc: Exception | None = None

    for attempt in range(settings.TELEGRAM_PUBLISH_MAX_RETRIES):
        _throttle()
        try:
            return send_fn()
        except Exception as exc:
            last_exc = exc
            exc_name = type(exc).__name__
            if exc_name == "RetryAfter":
                retry_after = getattr(exc, "retry_after", settings.TELEGRAM_FLOODWAIT_DEFAULT_SECONDS)
                time.sleep(float(retry_after))
                continue
            if "429" in str(exc):
                time.sleep(settings.TELEGRAM_FLOODWAIT_DEFAULT_SECONDS)
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError("telegram publish failed")


async def async_publish_with_retry(coro_factory: Callable[[], Coroutine[Any, Any, T]]) -> T:
    settings = get_settings()
    last_exc: Exception | None = None

    for attempt in range(settings.TELEGRAM_PUBLISH_MAX_RETRIES):
        _throttle()
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            exc_name = type(exc).__name__
            if exc_name == "RetryAfter":
                retry_after = getattr(exc, "retry_after", settings.TELEGRAM_FLOODWAIT_DEFAULT_SECONDS)
                await asyncio.sleep(float(retry_after))
                continue
            if "429" in str(exc):
                await asyncio.sleep(settings.TELEGRAM_FLOODWAIT_DEFAULT_SECONDS)
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError("telegram publish failed")
