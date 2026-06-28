"""Feed polling: first poll digests the new entries; a second poll de-dupes."""

from __future__ import annotations

import asyncio
import uuid

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("feedparser")

from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.output_format import OutputFormat  # noqa: E402
from artificial_writer.core.pipeline import PipelineResult  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import db as service_db  # noqa: E402
from artificial_writer.service import repository  # noqa: E402
from artificial_writer.service.jobs import tasks  # noqa: E402
from artificial_writer.service.models import Digest  # noqa: E402

_ENTRIES = [
    {"id": "entry-1", "link": "https://example.com/a", "title": "A"},
    {"id": "entry-2", "link": "https://example.com/b", "title": "B"},
]


class _FakeParsed:
    def __init__(self, entries: list[dict[str, str]]) -> None:
        self.entries = entries


def _patch_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        self: object,
        url: str,
        *,
        save: bool = False,
        output_format: OutputFormat = OutputFormat.PROSE,
    ) -> PipelineResult:
        return PipelineResult(
            article=FetchedArticle(url=url, title=f"Title {url}", text="body"),
            summary=SummaryResult(summary=f"summary of {url}", backend="extractive", model="m"),
        )

    monkeypatch.setattr(
        "artificial_writer.core.pipeline.build_summarizer", lambda settings: object()
    )
    monkeypatch.setattr("artificial_writer.core.pipeline.Pipeline.run", fake_run)


def _make_user_and_feed() -> tuple[str, str]:
    async def _run() -> tuple[str, str]:
        async with service_db.get_sessionmaker()() as session:
            user = await repository.create_user(
                session, email=f"{uuid.uuid4()}@example.com", password_hash="x"
            )
            await session.flush()
            feed = await repository.create_feed(
                session,
                user_id=user.id,
                rss_url="https://example.com/rss",
                cadence_minutes=60,
            )
            await session.commit()
            return str(user.id), str(feed.id)

    return asyncio.run(_run())


def _digest_count(user_id: str) -> int:
    async def _run() -> int:
        async with service_db.get_sessionmaker()() as session:
            return len(await repository.list_digests(session, uuid.UUID(user_id)))

    return asyncio.run(_run())


def _get_digest(digest_id: str) -> Digest | None:
    async def _run() -> Digest | None:
        async with service_db.get_sessionmaker()() as session:
            return await session.get(Digest, uuid.UUID(digest_id))

    return asyncio.run(_run())


def test_poll_creates_digest_then_dedupes(
    configured_service_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pipeline(monkeypatch)
    monkeypatch.setattr("feedparser.parse", lambda url: _FakeParsed(_ENTRIES))
    user_id, feed_id = _make_user_and_feed()

    # First poll: both entries are new -> one feed digest of 2 summaries.
    first = tasks.poll_feed(feed_id)
    assert first is not None
    digest = _get_digest(first)
    assert digest is not None
    assert digest.kind == "feed"
    assert len(digest.summary_ids) == 2

    # Second poll: the same entries are already in seen_entry_ids -> no digest.
    second = tasks.poll_feed(feed_id)
    assert second is None
    assert _digest_count(user_id) == 1
