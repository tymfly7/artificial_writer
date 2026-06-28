"""Async, per-user CRUD over the service models.

Every query is scoped by ``user_id`` so one tenant can never read another's
rows. :func:`search_summaries` uses PostgreSQL full-text search; callers running
on SQLite (tests) should skip the FTS path.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..core.config import get_settings
from ..core.fetchers import FetchedArticle
from ..core.summarizers import SummaryResult
from .models import ApiKey, Digest, Feed, Summary, UsageRecord, User

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


async def update_email(session: AsyncSession, *, user: User, email: str) -> None:
    """Replace ``user``'s login email (caller checks uniqueness first)."""
    user.email = email
    await session.flush()


async def update_password(
    session: AsyncSession, *, user: User, password_hash: str
) -> None:
    """Replace ``user``'s stored password hash."""
    user.password_hash = password_hash
    await session.flush()


async def delete_user(session: AsyncSession, user: User) -> None:
    """Delete a user and every row they own.

    The foreign keys carry no database-level cascade (so the schema stays
    portable across SQLite and Postgres), so each owned table is cleared
    explicitly before the user row itself.
    """
    for model in (ApiKey, Summary, Feed, Digest, UsageRecord):
        await session.execute(delete(model).where(model.user_id == user.id))
    await session.delete(user)
    await session.flush()


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


# --- Feeds -----------------------------------------------------------------------


async def create_feed(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    rss_url: str,
    cadence_minutes: int,
) -> Feed:
    """Persist a new RSS feed subscription owned by ``user_id``."""
    feed = Feed(user_id=user_id, rss_url=rss_url, cadence_minutes=cadence_minutes)
    session.add(feed)
    await session.flush()
    return feed


async def list_feeds(session: AsyncSession, user_id: uuid.UUID) -> list[Feed]:
    result = await session.execute(
        select(Feed).where(Feed.user_id == user_id).order_by(Feed.created_at.desc())
    )
    return list(result.scalars().all())


async def list_all_feeds(session: AsyncSession) -> list[Feed]:
    """Return every feed across all users (for the polling scheduler)."""
    result = await session.execute(select(Feed))
    return list(result.scalars().all())


async def get_feed(session: AsyncSession, feed_id: uuid.UUID) -> Feed | None:
    """Return a feed by id (not user-scoped; callers verify ownership)."""
    return await session.get(Feed, feed_id)


async def delete_feed(
    session: AsyncSession, *, user_id: uuid.UUID, feed_id: uuid.UUID
) -> bool:
    """Delete a user's feed; returns ``True`` if one was theirs and removed."""
    feed = await session.get(Feed, feed_id)
    if feed is None or feed.user_id != user_id:
        return False
    await session.delete(feed)
    await session.flush()
    return True


# --- Digests ---------------------------------------------------------------------


async def list_digests(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Digest]:
    result = await session.execute(
        select(Digest)
        .where(Digest.user_id == user_id)
        .order_by(Digest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_digest(
    session: AsyncSession, *, user_id: uuid.UUID, digest_id: uuid.UUID
) -> Digest | None:
    """Return a user's digest by id, or ``None`` if missing or not theirs."""
    digest = await session.get(Digest, digest_id)
    if digest is None or digest.user_id != user_id:
        return None
    return digest


async def get_summaries_for_digest(
    session: AsyncSession, *, user_id: uuid.UUID, summary_ids: Sequence[str]
) -> list[Summary]:
    """Return the user's summaries named in ``summary_ids``, in that order.

    Drives the structured (per-article) rendering of a digest. Ids that no
    longer resolve to one of the user's summaries are silently skipped, so a
    deleted source summary just disappears from the digest rather than erroring.
    """
    if not summary_ids:
        return []
    ids = [uuid.UUID(sid) for sid in summary_ids]
    result = await session.execute(
        select(Summary).where(Summary.user_id == user_id, Summary.id.in_(ids))
    )
    by_id = {s.id: s for s in result.scalars().all()}
    return [by_id[i] for i in ids if i in by_id]


async def delete_digest(
    session: AsyncSession, *, user_id: uuid.UUID, digest_id: uuid.UUID
) -> bool:
    """Delete a user's digest; returns ``True`` if one was theirs and removed."""
    digest = await session.get(Digest, digest_id)
    if digest is None or digest.user_id != user_id:
        return False
    await session.delete(digest)
    await session.flush()
    return True


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
