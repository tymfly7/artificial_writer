"""Per-tier policy and daily quota enforcement.

This module is the safety gate that keeps the paid summarizer backends
unreachable to anyone who is not an authorized, in-quota user. Two checks run
before any tokens are spent, and a third records what was spent:

* :func:`assert_backend_allowed` -- a tier may only use the backends its policy
  permits. A free tier (cost cap ``0``) can never reach a paid backend.
  Violations raise :class:`QuotaExceeded` with ``status=BACKEND_NOT_ALLOWED``
  (mapped to HTTP 403).
* :func:`assert_within_quota` -- a tier's daily request and cost caps are
  enforced against today's :class:`~..service.models.UsageRecord`. Violations
  raise :class:`QuotaExceeded` with ``status=CAP_EXCEEDED`` (mapped to HTTP 429).
* :func:`record_usage` -- accumulates the requests, tokens, and cost of each
  completed call into today's usage row.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Settings, SummarizerType, get_settings
from ..core.errors import QuotaExceeded
from ..core.summarizers import SummaryResult
from . import repository
from .models import User


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _backend_name(summarizer: str | SummarizerType) -> str:
    return summarizer.value if isinstance(summarizer, SummarizerType) else summarizer


def assert_backend_allowed(
    user_tier: str,
    summarizer: str | SummarizerType,
    *,
    settings: Settings | None = None,
) -> None:
    """Reject a backend the user's tier may not use.

    Free backends are always permitted. A paid backend is permitted only when the
    tier has a positive daily cost cap; otherwise this raises
    :class:`QuotaExceeded` (HTTP 403 semantics).
    """
    settings = settings or get_settings()
    backend = _backend_name(summarizer)

    if backend in settings.free_backends:
        return

    cost_cap = settings.tier_daily_cost_cap_usd.get(user_tier, 0.0)
    if backend in settings.paid_backends and cost_cap > 0:
        return

    raise QuotaExceeded(
        f"The '{user_tier}' tier is not permitted to use the '{backend}' backend.",
        status=QuotaExceeded.BACKEND_NOT_ALLOWED,
    )


async def assert_within_quota(
    session: AsyncSession,
    user: User,
    *,
    settings: Settings | None = None,
) -> None:
    """Reject a request that would exceed the tier's daily caps.

    Caps are enforced against today's recorded usage: if the request count has
    reached the tier's request cap, or recorded spend has reached its cost cap,
    raise :class:`QuotaExceeded` (HTTP 429 semantics). A cost cap of ``0`` means
    "no paid spend" and is enforced by :func:`assert_backend_allowed`, so it is
    not treated as an instant cost-cap breach here.
    """
    settings = settings or get_settings()
    request_cap = settings.tier_daily_request_cap.get(user.tier, 0)
    cost_cap = settings.tier_daily_cost_cap_usd.get(user.tier, 0.0)

    usage = await repository.get_usage(session, user, _today())
    requests = usage.requests if usage is not None else 0
    spent = usage.cost_usd if usage is not None else 0.0

    if requests >= request_cap:
        raise QuotaExceeded(
            f"Daily request cap of {request_cap} reached for the '{user.tier}' tier.",
            status=QuotaExceeded.CAP_EXCEEDED,
        )
    if cost_cap > 0 and spent >= cost_cap:
        raise QuotaExceeded(
            f"Daily cost cap of ${cost_cap:.2f} reached for the '{user.tier}' tier.",
            status=QuotaExceeded.CAP_EXCEEDED,
        )


async def record_usage(
    session: AsyncSession, user: User, result: SummaryResult
) -> None:
    """Accumulate the cost of a completed summary into today's usage row."""
    tokens = (result.input_tokens or 0) + (result.output_tokens or 0)
    await repository.add_usage(
        session,
        user=user,
        day=_today(),
        requests=1,
        tokens=tokens,
        cost_usd=result.cost_usd or 0.0,
    )
