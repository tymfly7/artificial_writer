"""Async SQLAlchemy engine, session factory, and the FastAPI session dependency.

The engine is created lazily so this module stays importable without a live
database (importing it never opens a connection). Tests swap in a SQLite engine
via :func:`configure_engine`; production reads ``settings.database_url``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from ..core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in this package."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory, creating it on first use."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


def configure_engine(engine: AsyncEngine) -> None:
    """Install an explicit engine (and matching sessionmaker).

    Used by tests to point the session dependency at an in-memory SQLite
    database without going through ``settings.database_url``.
    """
    global _engine, _sessionmaker
    _engine = engine
    _sessionmaker = async_sessionmaker(engine, expire_on_commit=False)


def reset_engine() -> None:
    """Forget the cached engine/sessionmaker (mainly for test isolation)."""
    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an :class:`AsyncSession`."""
    async with get_sessionmaker()() as session:
        yield session
