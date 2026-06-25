"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from artificial_writer.core.config import Settings, SummarizerType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

SAMPLE_HTML = """
<html>
  <head><title>The Future of Solar Power</title></head>
  <body>
    <nav>home about contact</nav>
    <p>Solar power is growing rapidly across the world. Costs have fallen dramatically.</p>
    <p>Engineers improve panel efficiency every single year. Storage remains a key challenge.</p>
    <p>Governments now offer incentives. Adoption is accelerating in many countries.</p>
    <script>console.log("ignore me");</script>
    <footer>copyright 2026</footer>
  </body>
</html>
"""

SAMPLE_TEXT = (
    "Solar power is growing rapidly across the world. Costs have fallen dramatically. "
    "Engineers are improving panel efficiency every single year. Storage remains a key challenge. "
    "Governments now offer incentives. Adoption is accelerating in many countries. "
    "Researchers continue to study new materials for cheaper cells."
)


@pytest.fixture
def extractive_settings() -> Settings:
    return Settings(summarizer=SummarizerType.EXTRACTIVE, extractive_sentences=2)


# --- Service-layer (async DB) fixtures -------------------------------------------
# Tests run against a file-backed SQLite database (aiosqlite) with NullPool so each
# connection is opened fresh in the current event loop -- this keeps the engine
# usable from both native async tests and Starlette's TestClient portal.


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"


async def _create_all(engine: AsyncEngine) -> None:
    from artificial_writer.service import models  # noqa: F401  (register tables)
    from artificial_writer.service.db import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def db_engine(sqlite_url: str) -> AsyncIterator[AsyncEngine]:
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(sqlite_url, poolclass=NullPool)
    await _create_all(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    from sqlalchemy.ext.asyncio import async_sessionmaker

    maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture
def service_client(sqlite_url: str) -> Iterator[object]:
    """A FastAPI TestClient wired to a fresh SQLite service database."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from artificial_writer.service import db as service_db
    from artificial_writer.web.app import app

    engine = create_async_engine(sqlite_url, poolclass=NullPool)
    asyncio.run(_create_all(engine))
    service_db.configure_engine(engine)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        asyncio.run(engine.dispose())
        service_db.reset_engine()
