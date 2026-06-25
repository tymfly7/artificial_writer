"""HTTP-level quota enforcement over the authenticated /api/summarize endpoint."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402

from artificial_writer.core.config import get_settings  # noqa: E402
from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.output_format import OutputFormat  # noqa: E402
from artificial_writer.core.pipeline import PipelineResult  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import db as service_db  # noqa: E402
from artificial_writer.service import repository  # noqa: E402
from artificial_writer.service.models import UsageRecord  # noqa: E402


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend: str = "extractive",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> None:
    """Replace the real fetch+summarize with a deterministic offline stub."""

    def fake_run(
        self: object,
        url: str,
        *,
        save: bool = False,
        output_format: OutputFormat = OutputFormat.PROSE,
    ) -> PipelineResult:
        return PipelineResult(
            article=FetchedArticle(url=url, title="T", text="body"),
            summary=SummaryResult(
                summary="summary",
                backend=backend,
                model="m",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            ),
        )

    # Never build a real (possibly paid) backend during Pipeline construction.
    monkeypatch.setattr(
        "artificial_writer.core.pipeline.build_summarizer", lambda settings: object()
    )
    monkeypatch.setattr("artificial_writer.core.pipeline.Pipeline.run", fake_run)


def _register(client: TestClient, email: str, password: str = "password123") -> None:
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201


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


def test_free_tier_anthropic_is_403(
    service_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pipeline(monkeypatch)
    _register(service_client, "free403@example.com")
    resp = service_client.post(
        "/api/summarize",
        json={"url": "https://example.com/a", "summarizer": "anthropic"},
    )
    assert resp.status_code == 403


def test_free_tier_request_cap_is_429(
    service_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pipeline(monkeypatch)
    monkeypatch.setitem(get_settings().tier_daily_request_cap, "free", 2)
    _register(service_client, "cap429@example.com")

    for _ in range(2):
        ok = service_client.post(
            "/api/summarize",
            json={"url": "https://example.com/a", "summarizer": "extractive"},
        )
        assert ok.status_code == 200

    blocked = service_client.post(
        "/api/summarize",
        json={"url": "https://example.com/a", "summarizer": "extractive"},
    )
    assert blocked.status_code == 429


def test_paid_user_usage_records_tokens_and_cost(
    service_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_pipeline(
        monkeypatch,
        backend="anthropic",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )
    _register(service_client, "pro@example.com")
    _set_tier("pro@example.com", "pro")

    resp = service_client.post(
        "/api/summarize",
        json={"url": "https://example.com/a", "summarizer": "anthropic"},
    )
    assert resp.status_code == 200
    assert resp.json()["backend"] == "anthropic"

    record = _usage("pro@example.com")
    assert record is not None
    assert record.requests == 1
    assert record.tokens == 150
    assert record.cost_usd == pytest.approx(0.01)
