"""HTTP-level account management over the authenticated web API."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402

EMAIL = "account@example.com"
PASSWORD = "password123"


def _register(client: TestClient, email: str = EMAIL, password: str = PASSWORD) -> None:
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201


def test_account_endpoints_require_auth(service_client: TestClient) -> None:
    assert service_client.get("/auth/me").status_code == 401
    assert (
        service_client.post(
            "/auth/email", json={"new_email": "x@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        service_client.post(
            "/auth/password",
            json={"current_password": "x", "new_password": "newpassword1"},
        ).status_code
        == 401
    )
    assert (
        service_client.request(
            "DELETE", "/auth/account", json={"password": PASSWORD}
        ).status_code
        == 401
    )


def test_me_returns_profile_and_caps(service_client: TestClient) -> None:
    _register(service_client)
    resp = service_client.get("/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["tier"] == "free"
    assert body["requests_today"] == 0
    assert body["cost_usd_today"] == 0.0
    # The free tier carries a request cap and no paid spend.
    assert body["daily_request_cap"] >= 1
    assert body["daily_cost_cap_usd"] == 0.0


def test_change_email(service_client: TestClient) -> None:
    _register(service_client)
    new_email = "corrected@example.com"

    # Wrong password is rejected; the email is unchanged.
    resp = service_client.post(
        "/auth/email", json={"new_email": new_email, "password": "wrongpass"}
    )
    assert resp.status_code == 401
    assert service_client.get("/auth/me").json()["email"] == EMAIL

    # Correct password rotates the login email.
    resp = service_client.post(
        "/auth/email", json={"new_email": new_email, "password": PASSWORD}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == new_email
    assert service_client.get("/auth/me").json()["email"] == new_email

    # The old email no longer logs in; the new one does.
    assert (
        service_client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        service_client.post(
            "/auth/login", json={"email": new_email, "password": PASSWORD}
        ).status_code
        == 200
    )


def test_change_email_rejects_address_taken_by_another_user(
    service_client: TestClient,
) -> None:
    # A second account exists; logged in as the first, we can't claim its email.
    _register(service_client, email="taken@example.com")
    service_client.post("/auth/logout")
    _register(service_client)

    resp = service_client.post(
        "/auth/email", json={"new_email": "taken@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 400
    assert service_client.get("/auth/me").json()["email"] == EMAIL


def test_change_password(service_client: TestClient) -> None:
    _register(service_client)
    new_password = "brandnewpass1"

    # Wrong current password is rejected.
    resp = service_client.post(
        "/auth/password",
        json={"current_password": "wrongpass", "new_password": new_password},
    )
    assert resp.status_code == 401

    # Correct current password rotates the credential.
    resp = service_client.post(
        "/auth/password",
        json={"current_password": PASSWORD, "new_password": new_password},
    )
    assert resp.status_code == 200

    # The old password no longer logs in; the new one does.
    assert (
        service_client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        service_client.post(
            "/auth/login", json={"email": EMAIL, "password": new_password}
        ).status_code
        == 200
    )


def test_delete_account(service_client: TestClient) -> None:
    _register(service_client)

    # A wrong password leaves the account intact.
    resp = service_client.request(
        "DELETE", "/auth/account", json={"password": "wrongpass"}
    )
    assert resp.status_code == 401
    assert service_client.get("/auth/me").status_code == 200

    # The correct password deletes the account and clears the session.
    resp = service_client.request("DELETE", "/auth/account", json={"password": PASSWORD})
    assert resp.status_code == 200
    assert service_client.get("/auth/me").status_code == 401

    # The credentials can no longer log in, and the email is free to reuse.
    assert (
        service_client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}
        ).status_code
        == 401
    )
    _register(service_client)
