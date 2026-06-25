"""Tests for password hashing, API keys, and session cookies."""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("passlib")

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from starlette.requests import Request  # noqa: E402

from artificial_writer.core.errors import AuthError  # noqa: E402
from artificial_writer.service import auth, repository  # noqa: E402


def _request(*, authorization: str | None = None, cookies: dict[str, str] | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    if cookies:
        cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers.append((b"cookie", cookie.encode()))
    return Request({"type": "http", "headers": headers})


def test_password_hash_and_verify() -> None:
    hashed = auth.hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert auth.verify_password("s3cret-password", hashed)
    assert not auth.verify_password("wrong", hashed)


def test_generate_api_key_shape() -> None:
    generated = auth.generate_api_key()
    assert generated.key.startswith("aw_")
    assert generated.prefix == generated.key[:8]
    assert generated.key_hash == auth.hash_api_key(generated.key)
    assert generated.key_hash != generated.key


def test_session_cookie_round_trip() -> None:
    user_id = uuid.uuid4()
    token = auth.make_session_token(user_id)
    assert auth.read_session_token(token) == user_id
    assert auth.read_session_token(token + "tampered") is None
    assert auth.read_session_token("not-a-token") is None


async def test_bearer_authentication_and_revocation(db_session: AsyncSession) -> None:
    user = await repository.create_user(
        db_session, email="a@example.com", password_hash=auth.hash_password("password1")
    )
    generated = auth.generate_api_key()
    await repository.create_api_key(
        db_session, user_id=user.id, key_hash=generated.key_hash, prefix=generated.prefix
    )
    await db_session.commit()

    # A valid Bearer key resolves to its owner.
    resolved = await auth.current_user(
        _request(authorization=f"Bearer {generated.key}"), db_session
    )
    assert resolved.id == user.id

    # After revocation the same key is rejected with AuthError (-> 401).
    key = await repository.get_api_key_by_hash(db_session, generated.key_hash)
    assert key is not None
    await repository.revoke_api_key(db_session, user_id=user.id, key_id=key.id)
    await db_session.commit()
    with pytest.raises(AuthError):
        await auth.current_user(
            _request(authorization=f"Bearer {generated.key}"), db_session
        )


async def test_session_cookie_authentication(db_session: AsyncSession) -> None:
    user = await repository.create_user(
        db_session, email="b@example.com", password_hash=auth.hash_password("password1")
    )
    await db_session.commit()
    token = auth.make_session_token(user.id)
    resolved = await auth.current_user(
        _request(cookies={auth.SESSION_COOKIE: token}), db_session
    )
    assert resolved.id == user.id


async def test_no_credentials_raises(db_session: AsyncSession) -> None:
    with pytest.raises(AuthError):
        await auth.current_user(_request(), db_session)
