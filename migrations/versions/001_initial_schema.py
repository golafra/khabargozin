"""Initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("credibility_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="general"),
        sa.Column("political_bias_tag", sa.String(64), nullable=True),
        sa.Column("is_primary_source", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_message_id", sa.BigInteger(), nullable=True),
        sa.Column("last_successful_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetch_error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("status_reason", sa.String(128), nullable=True),
        sa.Column("centroid_embedding", Vector(384), nullable=True),
        sa.Column("event_signature", sa.Text(), nullable=True),
        sa.Column("distinct_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("independent_source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_for_hold", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("topic", sa.String(64), nullable=True),
        sa.Column("sensitivity", sa.String(32), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_ai_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_independent_source_count_at_run", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clusters_status", "clusters", ["status"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("reply_to_message_id", sa.BigInteger(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("text_hash", sa.String(64), nullable=True),
        sa.Column("url", sa.String(512), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("media_meta", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edit_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_text", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("message_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "message_id", name="uq_messages_source_message"),
    )
    op.create_index("ix_messages_published_at", "messages", ["published_at"])
    op.create_index("ix_messages_cluster_id", "messages", ["cluster_id"])

    op.create_table(
        "ai_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("prompt_version", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("editorial_priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("headline", sa.Text(), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("why_it_matters", sa.Text(), nullable=False, server_default=""),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("sources_used", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("rejection_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("sensitivity", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_estimate_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "publication_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(32), nullable=False, server_default="initial"),
        sa.Column("event_key", sa.String(128), nullable=True),
        sa.Column("track", sa.String(16), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("rendered_text_hash", sa.String(64), nullable=False),
        sa.Column("payload_preview", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("send_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("""
        CREATE UNIQUE INDEX ix_outbox_initial_cluster_unique
        ON publication_outbox (cluster_id)
        WHERE operation_type = 'initial'
    """)
    op.execute("""
        CREATE UNIQUE INDEX ix_outbox_event_key_unique
        ON publication_outbox (cluster_id, operation_type, event_key)
        WHERE event_key IS NOT NULL
    """)

    op.create_table(
        "publications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("outbox_id", sa.Integer(), nullable=False),
        sa.Column("telegram_post_id", sa.Integer(), nullable=True),
        sa.Column("track", sa.String(16), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_retracted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"]),
        sa.ForeignKeyConstraint(["outbox_id"], ["publication_outbox.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hold_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id"),
    )

    op.create_table(
        "app_state",
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(128), nullable=True),
        sa.Column("old_status", sa.String(64), nullable=True),
        sa.Column("new_status", sa.String(64), nullable=True),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("decision_version", sa.String(32), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute("""
        CREATE INDEX ix_clusters_centroid_embedding
        ON clusters USING hnsw (centroid_embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("app_state")
    op.drop_table("hold_queue")
    op.drop_table("publications")
    op.drop_table("publication_outbox")
    op.drop_table("ai_results")
    op.drop_table("messages")
    op.drop_table("clusters")
    op.drop_table("sources")
