"""Authenticated multi-tenant summarize + archive endpoints.

These are the JSON API surface for logged-in users. Every call is owned by the
authenticated user, gated by the tier/quota policy, and persisted to that user's
archive. The unauthenticated HTML form in :mod:`artificial_writer.web.app` stays
available for local single-user use but is restricted to the free backends.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...service import repository
from ...service.auth import current_user
from ...service.db import get_session
from ...service.models import User
from ...service.schemas import SummarizeRequest, SummaryOut
from ...service.summarize_service import summarize_for_user

router = APIRouter(prefix="/api", tags=["summarize"])


@router.post("/summarize", response_model=SummaryOut)
async def summarize(
    req: SummarizeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SummaryOut:
    """Fetch and summarize ``req.url`` for the authenticated user and store it."""
    summary = await summarize_for_user(
        user,
        session=session,
        url=str(req.url),
        output_format=req.output_format,
        summarizer=req.summarizer,
        model=req.model,
    )
    await session.commit()
    return SummaryOut.model_validate(summary)


@router.get("/archive", response_model=list[SummaryOut])
async def archive(
    q: str = Query(..., min_length=1),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SummaryOut]:
    """Full-text search the authenticated user's archived summaries."""
    results = await repository.search_summaries(session, user, q)
    return [SummaryOut.model_validate(s) for s in results]
