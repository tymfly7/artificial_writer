"""Synchronous RQ task functions for batch summarization and feed polling.

RQ workers run synchronously, so each task is a thin sync wrapper that drives the
existing **async** service code via :func:`asyncio.run`. Reusing
:func:`summarize_for_user` keeps auth, the tier/quota gate, and cost accounting in
one place rather than duplicating that safety-critical logic for a sync path.

Quota policy for multi-URL work (batch / feed): each URL is summarized through
the same gated path. A URL that is rejected by the tier/quota gate (or fails to
fetch/summarize) is **skipped** -- it is logged, recorded as seen where relevant,
and omitted from the resulting digest. The digest therefore aggregates only the
URLs that actually succeeded (and may be empty if every URL was rejected).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import SummarizerType
from ...core.errors import ArtificialWriterError
from ...core.output_format import OutputFormat
from .. import digests, feeds, repository
from ..db import get_sessionmaker
from ..models import Summary, User
from ..summarize_service import summarize_for_user

logger = logging.getLogger(__name__)


def _fmt(output_format: str | None) -> OutputFormat | None:
    return OutputFormat(output_format) if output_format else None


def _summarizer(summarizer: str | None) -> SummarizerType | None:
    return SummarizerType(summarizer) if summarizer else None


# --- summarize a single URL ------------------------------------------------------


async def _summarize_url(
    user_id: uuid.UUID,
    url: str,
    output_format: str | None,
    summarizer: str | None,
    model: str | None,
) -> str:
    async with get_sessionmaker()() as session:
        user = await repository.get_user_by_id(session, user_id)
        if user is None:
            raise ValueError(f"Unknown user {user_id}")
        summary = await summarize_for_user(
            user,
            session=session,
            url=url,
            output_format=_fmt(output_format),
            summarizer=_summarizer(summarizer),
            model=model,
        )
        await session.commit()
        return str(summary.id)


def summarize_url(
    user_id: str,
    url: str,
    output_format: str | None = None,
    summarizer: str | None = None,
    model: str | None = None,
) -> str:
    """Summarize one URL for a user and return the stored summary id."""
    return asyncio.run(
        _summarize_url(uuid.UUID(user_id), url, output_format, summarizer, model)
    )


# --- batch: many URLs -> one digest ----------------------------------------------


async def _summarize_into(
    session: AsyncSession,
    user: User,
    url: str,
    output_format: str | None,
    summarizer: str | None,
    model: str | None,
) -> Summary | None:
    """Summarize one URL on an open session, returning the row or ``None`` if skipped."""
    try:
        return await summarize_for_user(
            user,
            session=session,
            url=url,
            output_format=_fmt(output_format),
            summarizer=_summarizer(summarizer),
            model=model,
        )
    except ArtificialWriterError as exc:
        logger.warning("Skipping %s in batch/feed: %s", url, exc)
        return None


async def _run_batch(
    user_id: uuid.UUID,
    urls: list[str],
    output_format: str | None,
    summarizer: str | None,
    model: str | None,
) -> str:
    async with get_sessionmaker()() as session:
        user = await repository.get_user_by_id(session, user_id)
        if user is None:
            raise ValueError(f"Unknown user {user_id}")
        rows: list[Summary] = []
        for url in urls:
            summary = await _summarize_into(
                session, user, url, output_format, summarizer, model
            )
            if summary is not None:
                rows.append(summary)
        title = f"Batch digest ({len(rows)} article{'s' if len(rows) != 1 else ''})"
        digest = await digests.build_digest(session, user.id, "batch", title, rows)
        await session.commit()
        return str(digest.id)


def run_batch(
    user_id: str,
    urls: list[str],
    output_format: str | None = None,
    summarizer: str | None = None,
    model: str | None = None,
) -> str:
    """Summarize every URL for a user and aggregate them into one stored digest."""
    return asyncio.run(
        _run_batch(uuid.UUID(user_id), urls, output_format, summarizer, model)
    )


# --- feed polling ----------------------------------------------------------------


async def _poll_feed(feed_id: uuid.UUID) -> str | None:
    async with get_sessionmaker()() as session:
        feed = await repository.get_feed(session, feed_id)
        if feed is None:
            logger.warning("poll_feed: feed %s no longer exists", feed_id)
            return None
        user = await repository.get_user_by_id(session, feed.user_id)
        if user is None:
            logger.warning("poll_feed: feed %s has no owner", feed_id)
            return None

        entries = feeds.parse_feed(feed.rss_url)
        fresh = feeds.new_entries(entries, feed.seen_entry_ids)
        if not fresh:
            feed.last_polled = datetime.now(timezone.utc)
            await session.commit()
            return None

        rows: list[Summary] = []
        for entry in fresh:
            summary = await _summarize_into(session, user, entry.link, None, None, None)
            if summary is not None:
                rows.append(summary)

        # Record every fresh entry as seen (even ones that failed) so we never
        # re-poll them, and reassign the list so SQLAlchemy flags the JSON change.
        feed.seen_entry_ids = [*feed.seen_entry_ids, *(e.id for e in fresh)]
        feed.last_polled = datetime.now(timezone.utc)

        if not rows:
            await session.commit()
            return None

        title = f"Feed digest ({len(rows)} new)"
        digest = await digests.build_digest(session, user.id, "feed", title, rows)
        await session.commit()
        return str(digest.id)


def poll_feed(feed_id: str) -> str | None:
    """Poll a feed for new entries; build a digest of any new ones (else ``None``)."""
    return asyncio.run(_poll_feed(uuid.UUID(feed_id)))
