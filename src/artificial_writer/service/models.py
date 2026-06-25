"""SQLAlchemy 2.0 typed ORM models for the multi-tenant service layer.

Every row is owned by a :class:`User`; the repository scopes all queries by
``user_id``. Models are written to create cleanly on both PostgreSQL (production)
and SQLite (tests). The PostgreSQL full-text GIN index is attached via a DDL
event guarded to ``postgresql`` only, so SQLite ``create_all`` stays happy.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    DDL,
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(32), default="free")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id"), index=True
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Summary(Base):
    __tablename__ = "summary"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id"), index=True
    )
    source_url: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(16))  # html/pdf/youtube/text
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)  # full original
    summary: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(String(16))
    backend: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class Feed(Base):
    __tablename__ = "feed"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id"), index=True
    )
    rss_url: Mapped[str] = mapped_column(Text)
    cadence_minutes: Mapped[int] = mapped_column(Integer)
    last_polled: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seen_entry_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Digest(Base):
    __tablename__ = "digest"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))  # "batch" / "feed"
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    summary_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class UsageRecord(Base):
    __tablename__ = "usage_record"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_usage_user_day"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id"), index=True
    )
    day: Mapped[date] = mapped_column(Date)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


# Postgres full-text search: a GIN index over to_tsvector(title || ' ' || summary).
# Attached only on PostgreSQL so SQLite ``create_all`` (used by tests) never sees it;
# the repository computes the same expression at query time. Mirrored in the migration.
FTS_INDEX_NAME = "ix_summary_fts"
_FTS_TSVECTOR = (
    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, ''))"
)
_create_fts_index = DDL(
    f"CREATE INDEX IF NOT EXISTS {FTS_INDEX_NAME} "
    f"ON summary USING gin ({_FTS_TSVECTOR})"
)
event.listen(
    Summary.__table__,
    "after_create",
    _create_fts_index.execute_if(dialect="postgresql"),
)
