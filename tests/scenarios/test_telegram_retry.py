"""Telegram FloodWait retry."""

from unittest.mock import patch

from app.publisher.telegram_retry import publish_with_retry


class RetryAfter(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after


def test_retry_after_then_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RetryAfter(0.01)
        return "ok"

    with patch("app.publisher.telegram_retry.time.sleep"):
        with patch("app.publisher.telegram_retry._throttle"):
            result = publish_with_retry(flaky)
    assert result == "ok"
    assert calls["n"] == 2
