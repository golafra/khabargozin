"""Redis advisory locks for Celery singleton tasks."""

import redis

from app.config import get_settings


def _redis_client() -> redis.Redis:
    return redis.from_url(get_settings().REDIS_URL, decode_responses=True)


def acquire_redis_lock(key: str, ttl: int) -> bool:
    client = _redis_client()
    return bool(client.set(key, "1", nx=True, ex=ttl))


def release_redis_lock(key: str) -> None:
    client = _redis_client()
    client.delete(key)
