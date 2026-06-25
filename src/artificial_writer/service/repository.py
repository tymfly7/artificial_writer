"""Async, per-user CRUD over the service models.

Every query is scoped by ``user_id`` so one tenant can never read another's
rows. :func:`search_summaries` uses PostgreSQL full-text search; callers running
on SQLite (tests) should skip the FTS path.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..core.config import get_settings
from ..core.fetchers import FetchedArticle
from ..core.summarizers import SummaryResult
from .models import ApiKey, Summary, UsageRecord, User

# --- Users -----------------------------------------------------------------------


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    tier: str | None = None,
) -> User:
    """Insert and return a new user (tier defaults to ``settings.default_tier``)."""
    user = User(
        email=email,
        password_hash=password_hash,
        tier=tier or get_settings().default_tier,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


# --- API keys --------------------------------------------------------------------


async def create_api_key(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    key_hash: str,
    prefix: str,
) -> ApiKey:
    """Persist a new API key (only its hash + prefix are stored)."""
    api_key = ApiKey(user_id=user_id, key_hash=key_hash, prefix=prefix)
    session.add(api_key)
    await session.flush()
    return api_key


async def get_api_key_by_hash(session: AsyncSession, key_hash: str) -> ApiKey | None:
    result = await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    return result.scalar_one_or_none()


async def list_api_keys(session: AsyncSession, user_id: uuid.UUID) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(
    session: AsyncSession, *, user_id: uuid.UUID, key_id: uuid.UUID
) -> ApiKey | None:
    """Mark a user's key revoked; returns the key, or ``None`` if not theirs."""
    api_key = await session.get(ApiKey, key_id)
    if api_key is None or api_key.user_id != user_id:
        return None
    if api_key.revoked_at is None:
        api_key.revoked_at = func.now()
        await session.flush()
    return api_key


# --- Summaries -------------------------------------------------------------------


async def save_summary(
    session: AsyncSession,
    *,
    user: User,
    article: FetchedArticle,
    result: SummaryResult,
    output_format: str,
    source_type: str,
) -> Summary:
    """Persist a finished summary owned by ``user`` and return the stored row."""
    summary = Summary(
        user_id=user.id,
        source_url=article.url,
        source_type=source_type,
        title=article.title,
        text=article.text,
        summary=result.summary,
        output_format=output_format,
        backend=result.backend,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
    )
    session.add(summary)
    await session.flush()
    return summary


async def list_summaries(
    session: AsyncSession,
    user: User,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Summary]:
    result = await session.execute(
        select(Summary)
        .where(Summary.user_id == user.id)
        .order_by(Summary.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


def _fts_vector() -> ColumnElement[Any]:
    """Build the ``to_tsvector(title || ' ' || summary)`` expression (Postgres)."""
    document = func.coalesce(Summary.title, "") + " " + func.coalesce(Summary.summary, "")
    return func.to_tsvector("english", document)


async def search_summaries(
    session: AsyncSession,
    user: User,
    q: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Summary]:
    """Full-text search a user's summaries (PostgreSQL only).

    Matches the GIN index defined on :class:`~..models.Summary`.
    """
    query = func.plainto_tsquery("english", q)
    result = await session.execute(
        select(Summary)
        .where(Summary.user_id == user.id)
        .where(_fts_vector().op("@@")(query))
        .order_by(Summary.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# --- Usage records ---------------------------------------------------------------


async def get_usage(
    session: AsyncSession, user: User, day: date
) -> UsageRecord | None:
    """Return ``user``'s usage row for ``day``, or ``None`` if none exists yet."""
    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.user_id == user.id, UsageRecord.day == day
        )
    )
    return result.scalar_one_or_none()


async def add_usage(
    session: AsyncSession,
    *,
    user: User,
    day: date,
    requests: int = 0,
    tokens: int = 0,
    cost_usd: float = 0.0,
) -> UsageRecord:
    """Upsert ``user``'s ``day`` usage row, accumulating the given amounts."""
    record = await get_usage(session, user, day)
    if record is None:
        record = UsageRecord(user_id=user.id, day=day, requests=0, tokens=0, cost_usd=0.0)
        session.add(record)
    record.requests += requests
    record.tokens += tokens
    record.cost_usd += cost_usd
    await session.flush()
    return record
