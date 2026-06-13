"""Config wiring for OpenAI timeout and DB pool."""

from unittest.mock import MagicMock, patch


def test_openai_client_passes_timeout(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "45")

    from app.config import get_settings

    get_settings.cache_clear()
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    with patch("app.ai.client.OpenAI", side_effect=fake_openai):
        from app.ai.client import AIClient

        AIClient()
    assert captured.get("timeout") == 45.0
    get_settings.cache_clear()


def test_engine_uses_pool_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setenv("DB_POOL_SIZE", "25")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "15")

    from app.config import get_settings
    from app.db import session as db_session_mod

    get_settings.cache_clear()
    db_session_mod.get_engine.cache_clear()

    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock()

    with patch("app.db.session.create_engine", side_effect=fake_create_engine):
        db_session_mod.get_engine()
    assert captured["pool_size"] == 25
    assert captured["max_overflow"] == 15
    assert captured["pool_pre_ping"] is True

    get_settings.cache_clear()
    db_session_mod.get_engine.cache_clear()
