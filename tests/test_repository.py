"""Tests for the per-user repository, including tenant isolation."""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import repository  # noqa: E402
from artificial_writer.service.models import User  # noqa: E402


async def _make_user(session: AsyncSession, email: str) -> User:
    return await repository.create_user(
        session, email=email, password_hash="x"
    )


def _article() -> FetchedArticle:
    return FetchedArticle(
        url="https://example.com/a", title="Solar Power", text="Body about solar."
    )


def _result() -> SummaryResult:
    return SummaryResult(
        summary="A short summary.",
        backend="extractive",
        model=None,
        input_tokens=10,
        output_tokens=5,
        cost_usd=None,
    )


async def test_save_and_list_summary(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "owner@example.com")
    saved = await repository.save_summary(
        db_session,
        user=user,
        article=_article(),
        result=_result(),
        output_format="prose",
        source_type="html",
    )
    assert saved.user_id == user.id
    assert saved.source_type == "html"

    listed = await repository.list_summaries(db_session, user)
    assert [s.id for s in listed] == [saved.id]
    assert listed[0].title == "Solar Power"


async def test_tenant_isolation(db_session: AsyncSession) -> None:
    user1 = await _make_user(db_session, "one@example.com")
    user2 = await _make_user(db_session, "two@example.com")
    await repository.save_summary(
        db_session,
        user=user1,
        article=_article(),
        result=_result(),
        output_format="prose",
        source_type="html",
    )

    assert len(await repository.list_summaries(db_session, user1)) == 1
    # A second user must not see the first user's summaries.
    assert await repository.list_summaries(db_session, user2) == []


async def test_get_user_by_email(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "find@example.com")
    found = await repository.get_user_by_email(db_session, "find@example.com")
    assert found is not None and found.id == user.id
    assert await repository.get_user_by_email(db_session, "missing@example.com") is None


@pytest.mark.skip(reason="Postgres full-text search is verified against Postgres in Phase E")
async def test_search_summaries_fts(db_session: AsyncSession) -> None:  # pragma: no cover
    user = await _make_user(db_session, "search@example.com")
    await repository.save_summary(
        db_session,
        user=user,
        article=_article(),
        result=_result(),
        output_format="prose",
        source_type="html",
    )
    hits = await repository.search_summaries(db_session, user, "solar")
    assert len(hits) == 1
