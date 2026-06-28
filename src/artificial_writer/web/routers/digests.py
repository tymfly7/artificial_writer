"""Authenticated digest viewing endpoints.

Digests are the stored, viewable output of batch runs and feed polls.
``GET /api/digests`` lists the authenticated user's digests; ``GET
/api/digests/{id}`` returns one as JSON, or as a simple HTML page when the
``Accept`` header prefers HTML (or ``?format=html`` is passed). All access is
scoped to the authenticated user.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from ...service import repository
from ...service.auth import current_user
from ...service.db import get_session
from ...service.models import User
from ...service.schemas import DigestOut

router = APIRouter(prefix="/api/digests", tags=["digests"])

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parents[1] / "templates"))


@router.get("", response_model=list[DigestOut])
async def list_digests(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DigestOut]:
    """List the authenticated user's digests, newest first."""
    digests = await repository.list_digests(session, user.id)
    return [DigestOut.model_validate(d) for d in digests]


@router.get("/{digest_id}")
async def get_digest(
    digest_id: uuid.UUID,
    request: Request,
    format: str | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Return one digest as JSON, or as HTML when HTML is preferred."""
    digest = await repository.get_digest(session, user_id=user.id, digest_id=digest_id)
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Digest not found.")

    wants_html = format == "html" or (
        format is None and "text/html" in request.headers.get("accept", "")
    )
    if wants_html:
        articles = await repository.get_summaries_for_digest(
            session, user_id=user.id, summary_ids=digest.summary_ids
        )
        return _TEMPLATES.TemplateResponse(
            request, "digest.html", {"digest": digest, "articles": articles}
        )
    return DigestOut.model_validate(digest)


@router.delete("/{digest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_digest(
    digest_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete one of the authenticated user's digests."""
    deleted = await repository.delete_digest(
        session, user_id=user.id, digest_id=digest_id
    )
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Digest not found.")
    await session.commit()
