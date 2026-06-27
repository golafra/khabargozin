"""Application settings — all business thresholds live here, not in logic."""

from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connections
    DATABASE_URL: str = "postgresql+psycopg2://khabargozin:khabargozin@localhost:5432/khabargozin"
    REDIS_URL: str = "redis://localhost:6379/0"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    OPENAI_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""

    # Publish
    PUBLISH_MODE: Literal["dry_run", "test", "production"] = "dry_run"
    TEST_OUTPUT_CHANNEL_ID: str = ""
    PRODUCTION_OUTPUT_CHANNEL_ID: str = ""

    # Cold start
    COLD_START_WARMUP_MINUTES: int = 20
    COLD_START_MIN_MESSAGES: int = 50
    COLD_START_DYNAMIC_AFTER_HOURS: int = 24

    # Threshold
    CLUSTER_PERCENTILE: float = 75.0
    MIN_CLUSTERS_FOR_PERCENTILE: int = 20
    CLUSTER_SCORE_FALLBACK_THRESHOLD: float = 6.0
    MIN_AI_SCORE_THRESHOLD: float = 5.5
    MAX_AI_SCORE_THRESHOLD: float = 8.0
    CLUSTER_ACTIVE_WINDOW_MINUTES: int = 360
    CLUSTER_LOOKBACK_HOURS: int = 24

    # Hold (phase 2)
    HOLD_EXPIRE_MINUTES: int = 60
    HOLD_MIN_SOURCES: int = 2
    HOLD_CONFIDENCE_THRESHOLD: float = 0.70

    # Fetcher
    FETCH_SLIDING_WINDOW: int = 20
    FETCH_TIME_OVERLAP_MINUTES: int = 60
    FETCH_PAGE_SIZE: int = 50
    FETCH_MAX_PAGES: int = 20
    FETCH_PAGINATION_DELAY_SECONDS: float = 4.0
    ICA_RATE_LIMIT_PER_MIN: int = 15
    ICA_FETCH_DELAY_SECONDS: float = 4.0
    SOURCE_STALE_ALERT_MINUTES: int = 120
    FETCHER_BACKEND: Literal["ica", "mock", "telethon"] = "ica"

    # Merge
    MERGE_OPEN_SIM: float = 0.72
    MERGE_OPEN_SIM_NER: float = 0.65
    MERGE_OPEN_SIM_TOPIC: float = 0.52
    MERGE_TOPIC_OVERLAP: float = 0.30
    MERGE_TOPIC_OVERLAP_STRONG: float = 0.42
    MERGE_PUBLISHED_SIM: float = 0.72
    MERGE_PUBLISHED_SIM_TOPIC: float = 0.55
    MERGE_PUBLISHED_SIM_HIGH: float = 0.85
    MERGE_PUBLISHED_NER: float = 0.50
    DUPLICATE_PUBLISH_SIM: float = 0.65
    DUPLICATE_PUBLISH_SIM_TOPIC: float = 0.50
    DUPLICATE_PUBLISH_HOURS: int = 24
    MERGE_EVENT_SIG: float = 0.40
    MERGE_NER_BOOST_THRESHOLD: float = 0.30
    SUPPLEMENT_MAX_DELTA_MINUTES: int = 720

    # Scorer
    SCORER_WEIGHT_SOURCES: float = 0.35
    SCORER_WEIGHT_CREDIBILITY: float = 0.30
    SCORER_WEIGHT_SPEED: float = 0.20
    SCORER_WEIGHT_URGENCY: float = 0.15
    SCORER_WEIGHT_TOPIC: float = 0.0
    SCORER_SOURCE_CAP: int = 4
    REPUBLISH_SIM_THRESHOLD: float = 0.95
    SCORER_SPEED_CAP_MINUTES: int = 60
    SCORER_URGENCY_KEYWORD_CAP: int = 3

    # AI
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = 30.0
    OPENAI_MAX_TOKENS: int = 800
    OPENAI_MONTHLY_BUDGET_USD: float = 15.0
    AI_JSON_MAX_RETRIES: int = 2
    PROMPT_VERSION: str = "v3"
    AI_SCHEMA_VERSION: str = "v1"
    FAST_MIN_CONFIDENCE: float = 0.75
    BATCH_MIN_CONFIDENCE: float = 0.60
    REJECT_CONFIDENCE: float = 0.40
    SENSITIVE_MIN_CONFIDENCE: float = 0.75
    RETRACTION_MIN_CONFIDENCE: float = 0.70

    # Batch publish
    BATCH_PUBLISH_INTERVAL_MINUTES: int = 15
    BATCH_PUBLISH_INTERVAL_BUSY_MINUTES: int = 5
    BATCH_QUEUE_BUSY_THRESHOLD: int = 5

    # Telegram
    TELEGRAM_PUBLISH_MIN_INTERVAL_SECONDS: float = 1.0
    TELEGRAM_PUBLISH_MAX_RETRIES: int = 3
    TELEGRAM_FLOODWAIT_DEFAULT_SECONDS: float = 5.0
    TELEGRAM_PARSE_MODE: str = "HTML"

    # Media
    MEDIA_MIN_ASPECT_RATIO: float = 0.5
    MEDIA_MAX_ASPECT_RATIO: float = 2.0
    MEDIA_MAX_VIDEO_SECONDS: int = 60
    MEDIA_MIN_PREVIEW_BYTES: int = 5000
    MEDIA_PREVIEW_ENABLED: bool = True

    # Clustering
    CLUSTER_BATCH_SIZE: int = 100

    # Hybrid clustering v4
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_PROVIDER: Literal["sentence_transformers", "offline"] = "sentence_transformers"
    RERANK_TOP_K: int = 3
    RERANK_MERGE_THRESHOLD: float = 0.75
    FINGERPRINT_PENALTY_WEIGHT: float = 0.25
    TOPIC_HARD_BLOCK_CONFIDENCE: float = 0.85
    TOPIC_SOFT_PENALTY_MISMATCH: float = 0.5
    MERGE_THRESHOLD_BREAKING: float = 0.78
    MERGE_THRESHOLD_ECONOMIC: float = 0.82
    MERGE_THRESHOLD_GENERAL: float = 0.80
    ANN_TOP_K_BREAKING: int = 20
    ANN_TOP_K_DEFAULT: int = 10
    ANN_TOP_K_MIN: int = 8
    PGVECTOR_EF_SEARCH: int = 40
    CLUSTER_STABILITY_WINDOW_HOURS: int = 6
    CONFIDENCE_AUTO_PUBLISH_MIN: int = 70
    STABILITY_AUTO_PUBLISH_MIN: int = 50
    BREAKING_PUBLISH_MIN_CONFIDENCE: int = 80
    BREAKING_VELOCITY_THRESHOLD: int = 5
    STABILITY_WEIGHT_BREAKING: float = 0.05
    CLUSTERING_OFFLINE: bool = False
    BEAT_RECONCILE_HOUR_UTC: int = 3

    # Fetch edit tracking
    FETCH_EDIT_LOOKBACK_HOURS: int = 48
    FETCH_EDIT_RECHECK_LIMIT: int = 30

    # Outbox
    OUTBOX_LOCK_TIMEOUT_MINUTES: int = 5

    # Archiving (phase 2)
    ARCHIVE_AFTER_DAYS: int = 35

    # Celery beat
    BEAT_FETCH_INTERVAL_SECONDS: int = 300
    BEAT_CLUSTER_INTERVAL_SECONDS: int = 300
    BEAT_AI_INTERVAL_SECONDS: int = 120
    BEAT_BATCH_PUBLISH_INTERVAL_SECONDS: int = 300
    BEAT_SOURCE_HEALTH_INTERVAL_SECONDS: int = 600
    BEAT_HOLD_CHECK_INTERVAL_SECONDS: int = 300
    TASK_LOCK_TTL_FETCH_SECONDS: int = 300
    TASK_LOCK_TTL_CLUSTER_SECONDS: int = 300
    TASK_LOCK_TTL_AI_SECONDS: int = 120
    TASK_LOCK_TTL_PUBLISH_SECONDS: int = 60
    CELERY_MAX_TASKS_PER_CHILD: int = 100

    # Audit
    DECISION_VERSION: str = "merge_v2"

    # App
    APP_START_TIME: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Admin panel
    ADMIN_PASSWORD: str = ""
    ADMIN_PORT: int = 8080

    @property
    def ica_min_interval_seconds(self) -> float:
        return 60.0 / max(self.ICA_RATE_LIMIT_PER_MIN, 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
