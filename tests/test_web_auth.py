"""End-to-end auth flow over HTTP: register -> login -> issue key."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402


def test_register_login_issue_key(service_client: TestClient) -> None:
    # Register starts a session (cookie stored in the client jar).
    resp = service_client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "user@example.com"

    # Login round-trips the same credentials.
    resp = service_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert resp.status_code == 200

    # Issuing a key returns the full secret exactly once.
    resp = service_client.post("/auth/keys")
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"].startswith("aw_")
    assert body["prefix"] == body["key"][:8]

    # Listing keys never exposes the secret again.
    resp = service_client.get("/auth/keys")
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) == 1
    assert keys[0]["key"] is None
    assert keys[0]["prefix"] == body["prefix"]


def test_bad_login_is_401(service_client: TestClient) -> None:
    service_client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": "password123"},
    )
    service_client.post("/auth/logout")  # drop the session cookie
    resp = service_client.post(
        "/auth/login",
        json={"email": "x@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_keys_require_auth(service_client: TestClient) -> None:
    resp = service_client.get("/auth/keys")
    assert resp.status_code == 401
