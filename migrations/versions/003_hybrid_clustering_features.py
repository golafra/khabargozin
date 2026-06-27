"""Hybrid clustering features — v4

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    # messages: features + processed_at; embedding dim change
    op.add_column("messages", sa.Column("features", postgresql.JSONB(), nullable=True))
    op.add_column("messages", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS embedding")
    op.add_column("messages", sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True))

    op.create_index("ix_messages_features_gin", "messages", ["features"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX ix_messages_features_topic ON messages ((features->>'topic'))"
    )
    op.execute(
        "CREATE INDEX ix_messages_features_keywords ON messages USING GIN ((features->'keywords'))"
    )
    op.execute(
        """
        CREATE INDEX ix_messages_embedding ON messages
        USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )

    # clusters: new hybrid fields + embedding dim
    op.add_column("clusters", sa.Column("anchor_message_id", sa.Integer(), nullable=True))
    op.add_column("clusters", sa.Column("event_fingerprint", postgresql.JSONB(), nullable=True))
    op.add_column("clusters", sa.Column("cluster_confidence", sa.SmallInteger(), nullable=True))
    op.add_column("clusters", sa.Column("cluster_stability", sa.SmallInteger(), nullable=True))
    op.add_column("clusters", sa.Column("cluster_debug", postgresql.JSONB(), nullable=True))
    op.add_column(
        "clusters",
        sa.Column("story_phase", sa.String(16), nullable=False, server_default="breaking"),
    )
    op.create_foreign_key(
        "fk_clusters_anchor_message",
        "clusters",
        "messages",
        ["anchor_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_clusters_story_phase", "clusters", ["story_phase"])
    op.create_index("ix_clusters_topic", "clusters", ["topic"])

    op.execute("ALTER TABLE clusters DROP COLUMN IF EXISTS centroid_embedding")
    op.add_column("clusters", sa.Column("centroid_embedding", Vector(EMBEDDING_DIM), nullable=True))

    op.execute("DROP INDEX IF EXISTS ix_clusters_centroid_embedding")
    op.execute(
        f"""
        CREATE INDEX ix_clusters_centroid_embedding ON clusters
        USING hnsw (centroid_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # ai_results versioning
    op.add_column("ai_results", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("ai_results", sa.Column("supersedes_id", sa.Integer(), nullable=True))
    op.add_column("ai_results", sa.Column("body", sa.Text(), nullable=False, server_default=""))
    op.create_foreign_key(
        "fk_ai_results_supersedes",
        "ai_results",
        "ai_results",
        ["supersedes_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # active learning
    op.create_table(
        "review_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("reviewer", sa.String(128), nullable=False, server_default="admin"),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("message_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("correct_cluster_id", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"]),
        sa.ForeignKeyConstraint(["correct_cluster_id"], ["clusters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_feedback_cluster_id", "review_feedback", ["cluster_id"])


def downgrade() -> None:
    op.drop_table("review_feedback")
    op.drop_constraint("fk_ai_results_supersedes", "ai_results", type_="foreignkey")
    op.drop_column("ai_results", "body")
    op.drop_column("ai_results", "supersedes_id")
    op.drop_column("ai_results", "version")

    op.execute("DROP INDEX IF EXISTS ix_clusters_centroid_embedding")
    op.execute("ALTER TABLE clusters DROP COLUMN IF EXISTS centroid_embedding")
    op.add_column("clusters", sa.Column("centroid_embedding", Vector(384), nullable=True))
    op.execute(
        """
        CREATE INDEX ix_clusters_centroid_embedding ON clusters
        USING hnsw (centroid_embedding vector_cosine_ops)
        """
    )

    op.drop_index("ix_clusters_topic", table_name="clusters")
    op.drop_index("ix_clusters_story_phase", table_name="clusters")
    op.drop_constraint("fk_clusters_anchor_message", "clusters", type_="foreignkey")
    op.drop_column("clusters", "story_phase")
    op.drop_column("clusters", "cluster_debug")
    op.drop_column("clusters", "cluster_stability")
    op.drop_column("clusters", "cluster_confidence")
    op.drop_column("clusters", "event_fingerprint")
    op.drop_column("clusters", "anchor_message_id")

    op.execute("DROP INDEX IF EXISTS ix_messages_embedding")
    op.execute("DROP INDEX IF EXISTS ix_messages_features_keywords")
    op.execute("DROP INDEX IF EXISTS ix_messages_features_topic")
    op.drop_index("ix_messages_features_gin", table_name="messages")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS embedding")
    op.add_column("messages", sa.Column("embedding", Vector(384), nullable=True))
    op.drop_column("messages", "processed_at")
    op.drop_column("messages", "features")
