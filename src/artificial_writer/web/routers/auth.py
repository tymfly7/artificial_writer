"""Authentication endpoints: register, login, logout, and API-key management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...core.errors import AuthError
from ...service import auth, repository
from ...service.db import get_session
from ...service.models import User
from ...service.quotas import today_usage
from ...service.schemas import (
    AccountDeleteRequest,
    AccountResponse,
    ApiKeyResponse,
    EmailChangeRequest,
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_session_token(user.id),
        httponly=True,
        samesite="lax",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Create a user and start a session."""
    if await repository.get_user_by_email(session, req.email) is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")
    user = await repository.create_user(
        session, email=req.email, password_hash=auth.hash_password(req.password)
    )
    await session.commit()
    _set_session_cookie(response, user)
    return {"id": str(user.id), "email": user.email}


@router.post("/login")
async def login(
    req: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Verify credentials and start a session."""
    user = await repository.get_user_by_email(session, req.email)
    if user is None or not auth.verify_password(req.password, user.password_hash):
        raise AuthError("Invalid email or password.")
    _set_session_cookie(response, user)
    return {"id": str(user.id), "email": user.email}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """Clear the session cookie."""
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"status": "ok"}


@router.get("/me", response_model=AccountResponse)
async def me(
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> AccountResponse:
    """Return the caller's profile alongside today's usage and tier caps."""
    settings = get_settings()
    requests, cost = await today_usage(session, user)
    return AccountResponse(
        id=user.id,
        email=user.email,
        tier=user.tier,
        created_at=user.created_at,
        requests_today=requests,
        cost_usd_today=cost,
        daily_request_cap=settings.tier_daily_request_cap.get(user.tier, 0),
        daily_cost_cap_usd=settings.tier_daily_cost_cap_usd.get(user.tier, 0.0),
    )


@router.post("/email")
async def change_email(
    req: EmailChangeRequest,
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Change the caller's login email after re-verifying their password."""
    if not auth.verify_password(req.password, user.password_hash):
        raise AuthError("Password is incorrect.")
    new_email = req.new_email.strip()
    if not new_email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email cannot be empty.")
    existing = await repository.get_user_by_email(session, new_email)
    if existing is not None and existing.id != user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")
    await repository.update_email(session, user=user, email=new_email)
    await session.commit()
    return {"id": str(user.id), "email": user.email}


@router.post("/password")
async def change_password(
    req: PasswordChangeRequest,
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Change the caller's password after re-verifying the current one."""
    if not auth.verify_password(req.current_password, user.password_hash):
        raise AuthError("Current password is incorrect.")
    await repository.update_password(
        session, user=user, password_hash=auth.hash_password(req.new_password)
    )
    await session.commit()
    return {"status": "ok"}


@router.delete("/account")
async def delete_account(
    req: AccountDeleteRequest,
    response: Response,
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Delete the caller's account and all their data after a password check."""
    if not auth.verify_password(req.password, user.password_hash):
        raise AuthError("Password is incorrect.")
    await repository.delete_user(session, user)
    await session.commit()
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"status": "deleted"}


@router.post("/keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyResponse:
    """Issue a new API key. The full secret is returned exactly once."""
    generated = auth.generate_api_key()
    api_key = await repository.create_api_key(
        session,
        user_id=user.id,
        key_hash=generated.key_hash,
        prefix=generated.prefix,
    )
    await session.commit()
    out = ApiKeyResponse.model_validate(api_key)
    out.key = generated.key
    return out


@router.get("/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyResponse]:
    """List the caller's API keys (secrets are never returned)."""
    keys = await repository.list_api_keys(session, user.id)
    return [ApiKeyResponse.model_validate(k) for k in keys]


@router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: uuid.UUID,
    user: User = Depends(auth.current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Revoke one of the caller's API keys."""
    api_key = await repository.revoke_api_key(session, user_id=user.id, key_id=key_id)
    if api_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found.")
    await session.commit()
    return {"status": "revoked", "id": str(api_key.id)}
