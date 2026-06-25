"""Authentication: password hashing, API keys, and session cookies.

Two credential types are supported, both resolved by the :func:`current_user`
dependency:

* ``Authorization: Bearer aw_...`` API keys — only a SHA-256 hash and an 8-char
  prefix are stored; the full key is shown to the caller exactly once.
* a signed ``aw_session`` cookie carrying the user id (itsdangerous).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.errors import AuthError
from . import repository
from .db import get_session
from .models import User

SESSION_COOKIE = "aw_session"
_API_KEY_PREFIX = "aw_"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Passwords -------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a bcrypt hash for ``password``."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether ``password`` matches the stored ``password_hash``."""
    return _pwd_context.verify(password, password_hash)


# --- API keys --------------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedKey:
    """A freshly minted API key: the secret plus what we persist for it."""

    key: str  # full secret, shown to the caller once
    key_hash: str  # sha256 hex, stored
    prefix: str  # first 8 chars, stored for identification


def hash_api_key(key: str) -> str:
    """Return the SHA-256 hex digest used to look an API key up."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_api_key() -> GeneratedKey:
    """Mint a new ``aw_`` API key and the hash/prefix to store for it."""
    key = _API_KEY_PREFIX + secrets.token_urlsafe(32)
    return GeneratedKey(key=key, key_hash=hash_api_key(key), prefix=key[:8])


# --- Session cookies -------------------------------------------------------------


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(get_settings().session_secret, salt=SESSION_COOKIE)


def make_session_token(user_id: uuid.UUID) -> str:
    """Return a signed token carrying ``user_id`` for the session cookie."""
    return _serializer().dumps(str(user_id))


def read_session_token(token: str) -> uuid.UUID | None:
    """Return the user id in a signed session token, or ``None`` if invalid."""
    try:
        raw = _serializer().loads(token)
    except BadSignature:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


# --- Dependency ------------------------------------------------------------------


async def _user_from_bearer(session: AsyncSession, header: str) -> User | None:
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    api_key = await repository.get_api_key_by_hash(session, hash_api_key(token.strip()))
    if api_key is None or api_key.revoked_at is not None:
        return None
    return await repository.get_user_by_id(session, api_key.user_id)


async def _user_from_cookie(session: AsyncSession, cookie: str) -> User | None:
    user_id = read_session_token(cookie)
    if user_id is None:
        return None
    return await repository.get_user_by_id(session, user_id)


async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    """Authenticate via a Bearer API key or the signed session cookie.

    Raises :class:`AuthError` (mapped to 401 by the app) when neither works.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header:
        user = await _user_from_bearer(session, auth_header)
        if user is not None:
            return user

    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        user = await _user_from_cookie(session, cookie)
        if user is not None:
            return user

    raise AuthError("Not authenticated.")
