"""Cross-cutting end-to-end flow over the authenticated multi-tenant API.

One TestClient-driven journey against a real Postgres (so per-user full-text
``/api/archive`` works) that ties the whole service together:

* register -> the session cookie AND an issued API key both authenticate;
* ``/api/summarize`` with ``output_format`` bullets vs tldr returns different
  shapes from a (mocked) LLM backend;
* the summary is searchable in ``/api/archive?q=`` and scoped to its owner
  (a second user sees nothing);
* a free tier hitting a paid backend gets 403, and an over-cap user gets 429,
  while a paid call records tokens + ``cost_usd``;
* ``/api/batch`` over several URLs builds one digest of N items;
* a feed registers, polls once (a digest) then again (a no-op);
* ``/api/digests`` lists the stored digests;
* a ``.pdf`` URL and a YouTube URL dispatch to the right fetcher.

Everything external (the LLM, the three fetchers, the RQ broker, the feed parser)
is mocked; only the app, the DB, and the quota logic are real. Skips when Docker
is unavailable (see the ``postgres_url`` fixture).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("fakeredis")
pytest.importorskip("rq")
pytest.importorskip("feedparser")

from artificial_writer.core.config import get_settings  # noqa: E402
from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.output_format import OutputFormat  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import db as service_db  # noqa: E402
from artificial_writer.service import repository  # noqa: E402
from artificial_writer.service.models import UsageRecord  # noqa: E402

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


# --- fakes ------------------------------------------------------------------------


class _FakeSummarizer:
    """A deterministic, network-free stand-in for a real summarizer backend.

    Shapes its output by ``output_format`` (so bullets and tldr genuinely differ)
    and reports the chosen backend plus token/cost metadata for paid backends.
    """

    def __init__(self, backend: str) -> None:
        self._backend = backend

    def summarize(
        self, text: str, *, output_format: OutputFormat = OutputFormat.PROSE
    ) -> SummaryResult:
        if output_format is OutputFormat.BULLETS:
            body = "- Solar costs are falling.\n- Adoption is accelerating."
        elif output_format is OutputFormat.TLDR:
            body = "TL;DR: Solar power keeps getting cheaper."
        else:
            body = "Solar power summary in prose form."
        paid = self._backend in ("openai", "anthropic")
        return SummaryResult(
            summary=body,
            backend=self._backend,
            model=f"mock-{self._backend}",
            input_tokens=100 if paid else None,
            output_tokens=50 if paid else None,
            cost_usd=0.01 if paid else None,
        )


def _install_fakes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Mock the LLM, the three fetchers, the RQ queue, and the feed scheduler.

    Returns a list that records which fetcher handled each URL, in order.
    """
    # LLM: build_summarizer returns our fake, keyed to the requested backend.
    monkeypatch.setattr(
        "artificial_writer.core.pipeline.build_summarizer",
        lambda settings: _FakeSummarizer(settings.summarizer.value),
    )

    # Fetchers: record which class handled the URL and return canned text. The
    # registry constructs each fetcher then calls .fetch, so patching the method
    # on the class covers every dispatch path without touching the network.
    routed: list[str] = []

    def _make(kind: str):
        def _fetch(self: object, source: str) -> FetchedArticle:
            routed.append(kind)
            return FetchedArticle(
                url=source,
                title=f"Solar report ({kind})",
                text="Solar power is growing. Costs have fallen.",
            )

        return _fetch

    monkeypatch.setattr(
        "artificial_writer.core.fetchers.html.HtmlFetcher.fetch", _make("html")
    )
    monkeypatch.setattr(
        "artificial_writer.core.fetchers.pdf.PdfFetcher.fetch", _make("pdf")
    )
    monkeypatch.setattr(
        "artificial_writer.core.fetchers.youtube.YouTubeFetcher.fetch", _make("youtube")
    )

    # RQ: an in-memory Redis-backed queue. We enqueue over HTTP, then drain it with
    # a SimpleWorker burst from the test thread -- the job's asyncio.run can't run
    # inside the app's event loop, and SimpleWorker doesn't fork (Windows-safe).
    from fakeredis import FakeStrictRedis
    from rq import Queue

    queue = Queue(connection=FakeStrictRedis())
    monkeypatch.setattr(
        "artificial_writer.service.jobs.queue.get_queue", lambda: queue
    )

    # Feeds: registering a feed must not reach a real scheduler/Redis.
    monkeypatch.setattr(
        "artificial_writer.service.jobs.scheduler.register_feed_schedules",
        lambda *a, **k: 0,
    )

    return routed


# --- DB helpers (the test needs to peek at server-side state) ---------------------


def _set_tier(email: str, tier: str) -> None:
    async def _run() -> None:
        async with service_db.get_sessionmaker()() as session:
            user = await repository.get_user_by_email(session, email)
            assert user is not None
            user.tier = tier
            await session.commit()

    asyncio.run(_run())


def _usage(email: str) -> UsageRecord | None:
    async def _run() -> UsageRecord | None:
        async with service_db.get_sessionmaker()() as session:
            user = await repository.get_user_by_email(session, email)
            assert user is not None
            return await repository.get_usage(
                session, user, datetime.now(timezone.utc).date()
            )

    return asyncio.run(_run())


def _feed_id_for(email: str) -> str:
    async def _run() -> str:
        async with service_db.get_sessionmaker()() as session:
            user = await repository.get_user_by_email(session, email)
            assert user is not None
            feeds = await repository.list_feeds(session, user.id)
            return str(feeds[0].id)

    return asyncio.run(_run())


# --- the flow ---------------------------------------------------------------------


def test_full_service_flow(
    pg_service_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    routed = _install_fakes(monkeypatch)
    client = pg_service_client

    # 1. Register the primary user (this sets the session cookie) and upgrade them
    #    to a paid tier so they can exercise the cloud backends.
    resp = client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    _set_tier("alice@example.com", "pro")

    # The session cookie authenticates...
    assert client.post("/auth/login",
                       json={"email": "alice@example.com", "password": "password123"}
                       ).status_code == 200

    # ...and so does a freshly-issued API key (used for the bearer calls below).
    key = client.post("/auth/keys").json()["key"]
    assert key.startswith("aw_")
    bearer = {"Authorization": f"Bearer {key}"}

    # 2. Same URL, two output formats, on a (mocked) LLM backend -> different shapes.
    bullets = client.post(
        "/api/summarize",
        headers=bearer,
        json={"url": "https://example.com/a", "summarizer": "anthropic",
              "output_format": "bullets"},
    ).json()
    tldr = client.post(
        "/api/summarize",
        headers=bearer,
        json={"url": "https://example.com/a", "summarizer": "anthropic",
              "output_format": "tldr"},
    ).json()
    assert bullets["summary"].startswith("- ")
    assert tldr["summary"].startswith("TL;DR:")
    assert bullets["summary"] != tldr["summary"]
    assert bullets["backend"] == "anthropic"

    # 6 (paid usage). The paid calls recorded tokens + cost.
    record = _usage("alice@example.com")
    assert record is not None
    assert record.requests == 2
    assert record.tokens == 2 * (100 + 50)
    assert record.cost_usd == pytest.approx(0.02)

    # 3. The stored summaries are searchable, scoped to their owner.
    hits = client.get("/api/archive", params={"q": "solar"}, headers=bearer).json()
    assert len(hits) == 2
    assert all("solar" in h["title"].lower() for h in hits)

    # A second user authenticates separately and sees none of Alice's archive.
    assert client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "password123"},
    ).status_code == 201
    bob_key = client.post("/auth/keys").json()["key"]
    bob = {"Authorization": f"Bearer {bob_key}"}
    assert client.get("/api/archive", params={"q": "solar"}, headers=bob).json() == []

    # 4. Bob is on the free tier: a paid backend is forbidden (403).
    assert client.post(
        "/api/summarize",
        headers=bob,
        json={"url": "https://example.com/x", "summarizer": "anthropic"},
    ).status_code == 403

    # 5. Free-tier daily request cap -> 429 once exceeded.
    monkeypatch.setitem(get_settings().tier_daily_request_cap, "free", 1)
    assert client.post(
        "/api/summarize",
        headers=bob,
        json={"url": "https://example.com/y", "summarizer": "extractive"},
    ).status_code == 200
    assert client.post(
        "/api/summarize",
        headers=bob,
        json={"url": "https://example.com/z", "summarizer": "extractive"},
    ).status_code == 429

    # 7. Batch several URLs (free backend) -> one digest with N items.
    urls = ["https://example.com/b1", "https://example.com/b2", "https://example.com/b3"]
    job = client.post(
        "/api/batch",
        headers=bearer,
        json={"urls": urls, "summarizer": "extractive", "output_format": "bullets"},
    ).json()

    from rq import SimpleWorker

    from artificial_writer.service.jobs import queue as job_queue

    worker_queue = job_queue.get_queue()
    SimpleWorker([worker_queue], connection=worker_queue.connection).work(burst=True)

    status = client.get(f"/api/batch/{job['job_id']}", headers=bearer).json()
    assert status["status"] == "finished"
    digest_id = status["digest_id"]
    assert digest_id is not None
    batch_digest = client.get(
        f"/api/digests/{digest_id}", headers={**bearer, "accept": "application/json"}
    ).json()
    assert batch_digest["kind"] == "batch"
    assert len(batch_digest["summary_ids"]) == len(urls)

    # 8. Register a feed, poll it twice: the first poll digests, the second no-ops.
    assert client.post(
        "/api/feeds",
        headers=bearer,
        json={"rss_url": "https://example.com/rss", "cadence_minutes": 60},
    ).status_code == 201
    feed_id = _feed_id_for("alice@example.com")

    from artificial_writer.service.jobs import tasks

    class _Parsed:
        entries = [
            {"id": "e1", "link": "https://example.com/f1", "title": "F1"},
            {"id": "e2", "link": "https://example.com/f2", "title": "F2"},
        ]

    monkeypatch.setattr("feedparser.parse", lambda url: _Parsed())
    first = tasks.poll_feed(feed_id)
    assert first is not None
    assert tasks.poll_feed(feed_id) is None  # already seen -> no-op

    # /api/digests now lists both the batch and the feed digest.
    digests = client.get("/api/digests", headers=bearer).json()
    kinds = sorted(d["kind"] for d in digests)
    assert kinds == ["batch", "feed"]

    # 9. A .pdf and a YouTube URL dispatch to their respective fetchers.
    routed.clear()
    client.post("/api/summarize", headers=bearer,
                json={"url": "https://example.com/paper.pdf", "summarizer": "extractive"})
    client.post("/api/summarize", headers=bearer,
                json={"url": "https://youtu.be/dQw4w9WgXcQ", "summarizer": "extractive"})
    assert routed == ["pdf", "youtube"]

    # Stored summaries also carry the source_type derived from the URL.
    archive = client.get("/api/archive", params={"q": "solar"}, headers=bearer).json()
    source_types = {h["source_type"] for h in archive}
    assert {"pdf", "youtube", "html"} <= source_types
