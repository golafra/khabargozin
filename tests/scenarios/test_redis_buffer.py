"""Redis buffer flush when DB recovers."""

import json
from unittest.mock import MagicMock, patch

import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.resilience.redis_buffer import buffer_message, flush_buffer


def test_buffer_flush_processes_all_items():
    server = fakeredis.FakeServer()
    client = fakeredis.FakeRedis(server=server, decode_responses=True)

    with patch("app.resilience.redis_buffer._client", return_value=client):
        buffer_message({"message_id": 1, "text": "a"})
        buffer_message({"message_id": 2, "text": "b"})
        seen = []

        def handler(payload):
            seen.append(payload["message_id"])

        count = flush_buffer(handler)
    assert count == 2
    assert seen == [1, 2]
