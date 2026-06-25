"""Tests for tier policy and daily quota enforcement (service/quotas.py)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from artificial_writer.core.config import get_settings  # noqa: E402
from artificial_writer.core.errors import QuotaExceeded  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import quotas, repository  # noqa: E402
from artificial_writer.service.models import User  # noqa: E402


async def _make_user(session: AsyncSession, email: str, tier: str = "free") -> User:
    return await repository.create_user(
        session, email=email, password_hash="x", tier=tier
    )


def _today() -> object:
    return datetime.now(timezone.utc).date()


# --- assert_backend_allowed ------------------------------------------------------


def test_free_tier_cannot_use_paid_backend() -> None:
    with pytest.raises(QuotaExceeded) as exc:
        quotas.assert_backend_allowed("free", "anthropic")
    assert exc.value.status == QuotaExceeded.BACKEND_NOT_ALLOWED


def test_paid_tier_may_use_paid_backend() -> None:
    quotas.assert_backend_allowed("pro", "anthropic")  # does not raise


def test_any_tier_may_use_free_backend() -> None:
    quotas.assert_backend_allowed("free", "extractive")  # does not raise


# --- assert_within_quota ---------------------------------------------------------


async def test_fresh_user_is_within_quota(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "fresh@example.com")
    await quotas.assert_within_quota(db_session, user)  # no usage yet -> allowed


async def test_request_cap_blocks_when_reached(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "cap@example.com")
    cap = get_settings().tier_daily_request_cap["free"]
    await repository.add_usage(db_session, user=user, day=_today(), requests=cap)
    with pytest.raises(QuotaExceeded) as exc:
        await quotas.assert_within_quota(db_session, user)
    assert exc.value.status == QuotaExceeded.CAP_EXCEEDED


async def test_cost_cap_blocks_when_reached(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "cost@example.com", tier="pro")
    cap = get_settings().tier_daily_cost_cap_usd["pro"]
    await repository.add_usage(db_session, user=user, day=_today(), cost_usd=cap)
    with pytest.raises(QuotaExceeded) as exc:
        await quotas.assert_within_quota(db_session, user)
    assert exc.value.status == QuotaExceeded.CAP_EXCEEDED


# --- record_usage ----------------------------------------------------------------


async def test_record_usage_increments_and_accumulates(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "rec@example.com", tier="pro")
    result = SummaryResult(
        summary="s",
        backend="anthropic",
        model="claude-haiku-4-5",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )
    await quotas.record_usage(db_session, user, result)
    await quotas.record_usage(db_session, user, result)

    record = await repository.get_usage(db_session, user, _today())
    assert record is not None
    assert record.requests == 2
    assert record.tokens == 300
    assert record.cost_usd == pytest.approx(0.02)
