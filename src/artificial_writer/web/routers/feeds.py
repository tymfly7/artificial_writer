"""Authenticated RSS feed-subscription endpoints.

Users register feeds to be polled on a cadence; each registration also schedules
the recurring :func:`..jobs.tasks.poll_feed` job. Listing and deletion are scoped
to the authenticated user.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...service import repository
from ...service.auth import current_user
from ...service.db import get_session
from ...service.jobs import scheduler as feed_scheduler
from ...service.models import User
from ...service.schemas import FeedCreate, FeedOut

router = APIRouter(prefix="/api/feeds", tags=["feeds"])


@router.post("", response_model=FeedOut, status_code=status.HTTP_201_CREATED)
async def create_feed(
    req: FeedCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FeedOut:
    """Subscribe the authenticated user to a feed and schedule its polling."""
    feed = await repository.create_feed(
        session,
        user_id=user.id,
        rss_url=str(req.rss_url),
        cadence_minutes=req.cadence_minutes,
    )
    await session.commit()
    feed_scheduler.register_feed_schedules()
    return FeedOut.model_validate(feed)


@router.get("", response_model=list[FeedOut])
async def list_feeds(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[FeedOut]:
    """List the authenticated user's feed subscriptions."""
    feeds = await repository.list_feeds(session, user.id)
    return [FeedOut.model_validate(f) for f in feeds]


@router.delete("/{feed_id}")
async def delete_feed(
    feed_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Delete one of the authenticated user's feeds and refresh the schedule."""
    deleted = await repository.delete_feed(session, user_id=user.id, feed_id=feed_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feed not found.")
    await session.commit()
    feed_scheduler.register_feed_schedules()
    return {"status": "deleted", "id": str(feed_id)}
