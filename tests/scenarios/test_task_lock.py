"""Task singleton lock."""

from unittest.mock import MagicMock, patch

from app.resilience.task_lock import acquire_redis_lock


def test_lock_acquire_once():
    mock_redis = MagicMock()
    mock_redis.set.return_value = True
    with patch("app.resilience.task_lock._redis_client", return_value=mock_redis):
        assert acquire_redis_lock("task:test", 60) is True
        mock_redis.set.assert_called_with("task:test", "1", nx=True, ex=60)


def test_lock_fails_when_held():
    mock_redis = MagicMock()
    mock_redis.set.return_value = False
    with patch("app.resilience.task_lock._redis_client", return_value=mock_redis):
        assert acquire_redis_lock("task:test", 60) is False
