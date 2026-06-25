"""initial schema: users, api keys, summaries, feeds, digests, usage + FTS index

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-25

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from artificial_writer.service.models import FTS_INDEX_NAME

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Matches Summary.title || ' ' || summary in models.py / repository.search_summaries.
_FTS_DDL = (
    f"CREATE INDEX IF NOT EXISTS {FTS_INDEX_NAME} ON summary "
    "USING gin (to_tsvector('english', "
    "coalesce(title, '') || ' ' || coalesce(summary, '')))"
)


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "api_key",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_user_id", "api_key", ["user_id"])
    op.create_index("ix_api_key_key_hash", "api_key", ["key_hash"], unique=True)

    op.create_table(
        "summary",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("output_format", sa.String(length=16), nullable=False),
        sa.Column("backend", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_summary_user_id", "summary", ["user_id"])
    op.create_index("ix_summary_created_at", "summary", ["created_at"])

    op.create_table(
        "feed",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rss_url", sa.Text(), nullable=False),
        sa.Column("cadence_minutes", sa.Integer(), nullable=False),
        sa.Column("last_polled", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_entry_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feed_user_id", "feed", ["user_id"])

    op.create_table(
        "digest",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("summary_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_digest_user_id", "digest", ["user_id"])

    op.create_table(
        "usage_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "day", name="uq_usage_user_day"),
    )
    op.create_index("ix_usage_record_user_id", "usage_record", ["user_id"])

    # PostgreSQL full-text GIN index over the summary's title + summary.
    op.execute(_FTS_DDL)


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {FTS_INDEX_NAME}")
    op.drop_index("ix_usage_record_user_id", table_name="usage_record")
    op.drop_table("usage_record")
    op.drop_index("ix_digest_user_id", table_name="digest")
    op.drop_table("digest")
    op.drop_index("ix_feed_user_id", table_name="feed")
    op.drop_table("feed")
    op.drop_index("ix_summary_created_at", table_name="summary")
    op.drop_index("ix_summary_user_id", table_name="summary")
    op.drop_table("summary")
    op.drop_index("ix_api_key_key_hash", table_name="api_key")
    op.drop_index("ix_api_key_user_id", table_name="api_key")
    op.drop_table("api_key")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
