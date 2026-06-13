"""Redis buffer when PostgreSQL unavailable — phase 2."""

import json
from typing import Any

import redis

from app.config import get_settings

BUFFER_KEY = "khabargozin:pg_buffer"


def _client() -> redis.Redis:
    return redis.from_url(get_settings().REDIS_URL, decode_responses=True)


def buffer_message(payload: dict[str, Any]) -> None:
    _client().rpush(BUFFER_KEY, json.dumps(payload, default=str))


def flush_buffer(handler) -> int:
    client = _client()
    count = 0
    while True:
        item = client.lpop(BUFFER_KEY)
        if not item:
            break
        handler(json.loads(item))
        count += 1
    return count


def buffer_length() -> int:
    return _client().llen(BUFFER_KEY)
