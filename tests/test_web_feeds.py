"""HTTP-level feed + digest endpoints over the authenticated web API."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402


def _register(client: TestClient, email: str = "feeduser@example.com") -> None:
    resp = client.post("/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 201


def test_feed_register_list_delete_and_digests(
    service_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Registering a feed schedules its polling; stub that out so the request
    # never reaches a real Redis/scheduler.
    monkeypatch.setattr(
        "artificial_writer.service.jobs.scheduler.register_feed_schedules",
        lambda *args, **kwargs: 0,
    )
    _register(service_client)

    # Create.
    resp = service_client.post(
        "/api/feeds",
        json={"rss_url": "https://example.com/rss", "cadence_minutes": 30},
    )
    assert resp.status_code == 201
    feed = resp.json()
    assert feed["cadence_minutes"] == 30
    assert feed["last_polled"] is None

    # List.
    resp = service_client.get("/api/feeds")
    assert resp.status_code == 200
    assert [f["id"] for f in resp.json()] == [feed["id"]]

    # No digests have been produced yet.
    resp = service_client.get("/api/digests")
    assert resp.status_code == 200
    assert resp.json() == []

    # Delete.
    resp = service_client.delete(f"/api/feeds/{feed['id']}")
    assert resp.status_code == 200
    assert service_client.get("/api/feeds").json() == []


def test_feed_endpoints_require_auth(service_client: TestClient) -> None:
    assert service_client.get("/api/feeds").status_code == 401
    assert service_client.get("/api/digests").status_code == 401
