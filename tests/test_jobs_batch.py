"""Batch job: many URLs -> one stored digest, with the quota gate still applied."""

from __future__ import annotations

import asyncio
import uuid

import pytest

pytest.importorskip("sqlalchemy")

from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.output_format import OutputFormat  # noqa: E402
from artificial_writer.core.pipeline import PipelineResult  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import db as service_db  # noqa: E402
from artificial_writer.service import repository  # noqa: E402
from artificial_writer.service.jobs import tasks  # noqa: E402
from artificial_writer.service.models import Digest  # noqa: E402

URLS = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]


def _patch_pipeline(monkeypatch: pytest.MonkeyPatch, *, backend: str = "extractive") -> None:
    """Replace fetch+summarize with a deterministic offline stub."""

    def fake_run(
        self: object,
        url: str,
        *,
        save: bool = False,
        output_format: OutputFormat = OutputFormat.PROSE,
    ) -> PipelineResult:
        return PipelineResult(
            article=FetchedArticle(url=url, title=f"Title {url}", text="body"),
            summary=SummaryResult(summary=f"summary of {url}", backend=backend, model="m"),
        )

    monkeypatch.setattr(
        "artificial_writer.core.pipeline.build_summarizer", lambda settings: object()
    )
    monkeypatch.setattr("artificial_writer.core.pipeline.Pipeline.run", fake_run)


def _make_user(tier: str = "free") -> str:
    async def _run() -> str:
        async with service_db.get_sessionmaker()() as session:
            user = await repository.create_user(
                session, email=f"{uuid.uuid4()}@example.com", password_hash="x", tier=tier
            )
            await session.commit()
            return str(user.id)

    return asyncio.run(_run())


def _get_digest(digest_id: str) -> Digest | None:
    async def _run() -> Digest | None:
        async with service_db.get_sessionmaker()() as session:
            return await session.get(Digest, uuid.UUID(digest_id))

    return asyncio.run(_run())


def test_batch_three_urls_makes_one_digest(
    configured_service_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pipeline(monkeypatch)
    user_id = _make_user()

    digest_id = tasks.run_batch(user_id, URLS, "prose", "extractive", None)

    digest = _get_digest(digest_id)
    assert digest is not None
    assert digest.kind == "batch"
    assert len(digest.summary_ids) == 3
    # The rendered body covers every article.
    assert digest.body.count("## ") == 3


def test_batch_quota_gate_skips_disallowed_backend(
    configured_service_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Policy: a free-tier user requesting a paid backend has every URL rejected
    # by the quota gate, so the batch still completes but its digest is empty.
    _patch_pipeline(monkeypatch, backend="anthropic")
    user_id = _make_user(tier="free")

    digest_id = tasks.run_batch(user_id, URLS, "prose", "anthropic", None)

    digest = _get_digest(digest_id)
    assert digest is not None
    assert digest.summary_ids == []
