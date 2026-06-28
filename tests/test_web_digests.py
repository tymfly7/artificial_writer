"""HTTP-level digest management: structured HTML rendering and deletion."""

from __future__ import annotations

import asyncio
import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402

from artificial_writer.core.fetchers import FetchedArticle  # noqa: E402
from artificial_writer.core.summarizers import SummaryResult  # noqa: E402
from artificial_writer.service import db as service_db  # noqa: E402
from artificial_writer.service import repository  # noqa: E402
from artificial_writer.service.digests import build_digest  # noqa: E402
from artificial_writer.service.models import User  # noqa: E402


def _register(client: TestClient, email: str = "digester@example.com") -> uuid.UUID:
    resp = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201
    return uuid.UUID(client.get("/auth/me").json()["id"])


def _seed_digest(user_id: uuid.UUID) -> uuid.UUID:
    """Create two summaries and a batch digest over them for ``user_id``."""

    async def _run() -> uuid.UUID:
        async with service_db.get_sessionmaker()() as session:
            user = await session.get(User, user_id)
            assert user is not None
            rows = []
            for n in (1, 2):
                row = await repository.save_summary(
                    session,
                    user=user,
                    article=FetchedArticle(
                        url=f"https://example.com/{n}", title=f"Article {n}", text="body"
                    ),
                    result=SummaryResult(
                        summary=f"Summary number {n}.", backend="extractive", model=None
                    ),
                    output_format="prose",
                    source_type="html",
                )
                rows.append(row)
            digest = await build_digest(session, user.id, "batch", "My Batch", rows)
            await session.commit()
            return digest.id

    return asyncio.run(_run())


def test_digest_html_renders_structured_articles(service_client: TestClient) -> None:
    user_id = _register(service_client)
    digest_id = _seed_digest(user_id)

    resp = service_client.get(f"/api/digests/{digest_id}?format=html")
    assert resp.status_code == 200
    body = resp.text
    # Each article's title, source URL, and summary are rendered separately —
    # not dumped as one markdown blob.
    assert "Article 1" in body and "Article 2" in body
    assert "https://example.com/1" in body and "https://example.com/2" in body
    assert "Summary number 1." in body and "Summary number 2." in body
    assert 'class="article"' in body


def test_digest_delete_is_user_scoped(service_client: TestClient) -> None:
    user_id = _register(service_client)
    digest_id = _seed_digest(user_id)

    assert len(service_client.get("/api/digests").json()) == 1

    # Delete removes it.
    assert service_client.delete(f"/api/digests/{digest_id}").status_code == 204
    assert service_client.get("/api/digests").json() == []

    # Deleting a missing digest is a 404.
    assert service_client.delete(f"/api/digests/{uuid.uuid4()}").status_code == 404


def test_digest_endpoints_require_auth(service_client: TestClient) -> None:
    assert service_client.delete(f"/api/digests/{uuid.uuid4()}").status_code == 401
