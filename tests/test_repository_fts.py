"""PostgreSQL full-text search for the archive (real Postgres via testcontainers).

This is the one Postgres-backed test that exercises ``search_summaries`` against
the actual ``to_tsvector``/``plainto_tsquery`` path and the GIN index created by
``Base.metadata.create_all``. It skips when Docker/testcontainers is unavailable;
the SQLite suites keep their FTS cases skipped (see ``test_repository.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("sqlalchemy")

from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import repository  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from artificial_writer.service.models import User


async def _make_user(session: AsyncSession, email: str) -> User:
    return await repository.create_user(session, email=email, password_hash="x")


async def _save(session: AsyncSession, user: User, *, title: str, summary: str) -> None:
    await repository.save_summary(
        session,
        user=user,
        article=FetchedArticle(url="https://example.com", title=title, text="body"),
        result=SummaryResult(summary=summary, backend="extractive", model=None),
        output_format="prose",
        source_type="html",
    )


async def test_search_filters_and_scopes_per_user(pg_session: AsyncSession) -> None:
    alice = await _make_user(pg_session, "alice@example.com")
    bob = await _make_user(pg_session, "bob@example.com")

    await _save(pg_session, alice, title="The Future of Solar Power", summary="Panels get cheaper.")
    await _save(pg_session, alice, title="Wind Turbines", summary="Offshore wind expands fast.")
    # Bob also has a 'solar' summary -- it must never surface in Alice's results.
    await _save(pg_session, bob, title="Solar in the desert", summary="A bob-only article.")
    await pg_session.flush()

    # Filters: a query returns only the matching row(s) for that user.
    solar = await repository.search_summaries(pg_session, alice, "solar")
    assert [s.title for s in solar] == ["The Future of Solar Power"]

    wind = await repository.search_summaries(pg_session, alice, "offshore wind")
    assert [s.title for s in wind] == ["Wind Turbines"]

    # Stemming: "panel" matches the stored "Panels".
    assert len(await repository.search_summaries(pg_session, alice, "panel")) == 1

    # No match -> empty; scoping -> Bob's solar row is invisible to Alice.
    assert await repository.search_summaries(pg_session, alice, "nonexistentword") == []
    assert await repository.search_summaries(pg_session, bob, "solar")  # Bob sees his own
    bob_titles = [s.title for s in await repository.search_summaries(pg_session, bob, "solar")]
    assert bob_titles == ["Solar in the desert"]
