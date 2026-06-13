"""Shared test fixtures."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://khabargozin:khabargozin@localhost:5432/khabargozin_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("FETCHER_BACKEND", "mock")
os.environ.setdefault("PUBLISH_MODE", "dry_run")
os.environ.setdefault("OPENAI_API_KEY", "")
