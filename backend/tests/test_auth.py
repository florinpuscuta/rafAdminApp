"""Teste pentru modulul auth: signup, login, /me, change-password, password reset.

Notă despre rate-limit: pentru teste care NU verifică explicit rate-limit,
`client` fixture dă un X-Forwarded-For unic per test. Testul de rate-limit
folosește un IP fix pentru toate requesturile consecutive.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app


pytestmark = pytest.mark.asyncio


# ── signup ────────────────────────────────────────────────────────────────


async def test_signup_happy_path(client: AsyncClient):
    email = f"new-{uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Acme Co", "email": email, "password": "Parola_Test_1234"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["accessToken"]
    assert data["tokenType"] == "bearer"
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "admin"
    assert data["tenant"]["name"] == "Acme Co"
    assert data["tenant"]["slug"] == "acme-co"
    assert data["tenant"]["active"] is True


async def test_signup_duplicate_email_409(client: AsyncClient, signup_user):
    first = await signup_user(email=f"dup-{uuid4().hex[:8]}@example.com")
    email = first["email"]
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Other Co", "email": email, "password": "Parola_Test_1234"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "email_taken"


async def test_signup_weak_password_422(client: AsyncClient):
    resp = await client.post(
        "/api/auth/signup",
        json={
            "tenantName": "Acme",
            "email": "weak@example.com",
            "password": "short",  # <8 chars
        },
    )
    assert resp.status_code == 422


# ── login ─────────────────────────────────────────────────────────────────


async def test_login_happy_path(client: AsyncClient, signup_user):
    user = await signup_user()
    resp = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accessToken"]
    assert data["user"]["email"] == user["email"]


async def test_login_wrong_password_401(client: AsyncClient, signup_user):
    user = await signup_user()
    resp = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "wrongwrongwrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


async def test_login_unknown_email_401(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "Parola_Test_1234"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


async def test_login_rate_limit_429_after_5_attempts(signup_user):
    """Slowapi limiter: 5/minute pe login. Al 6-lea request → 429.

    `signup_user` merge pe client-ul default (IP per-test, nu afectează IP-ul
    fix pentru login). Login-ul merge pe un IP dedicat pentru ca contorul
    slowapi să fie clean.
    """
    user = await signup_user()
    fixed_ip = "10.99.99.99"
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
        headers={"X-Forwarded-For": fixed_ip},
    ) as ac:
        # 5 fails → account lockout (401 invalid_credentials, contorul ajunge la 5)
        for i in range(5):
            r = await ac.post(
                "/api/auth/login",
                json={"email": user["email"], "password": "wrongwrongwrong"},
            )
            assert r.status_code == 401, f"attempt #{i + 1} got {r.status_code}"
            assert r.json()["detail"]["code"] == "invalid_credentials"
        # Al 6-lea: contul e locked → 401 account_locked (NU 429 — rate limit
        # IP e setat la 15/min pentru a lăsa spațiu pentru lockout-ul per-cont).
        r = await ac.post(
            "/api/auth/login",
            json={"email": user["email"], "password": "wrongwrongwrong"},
        )
        assert r.status_code == 401, r.text
        assert r.json()["detail"]["code"] == "account_locked"


# ── /me ───────────────────────────────────────────────────────────────────


async def test_me_authenticated(client: AsyncClient, admin_ctx):
    resp = await client.get("/api/auth/me", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == admin_ctx["email"]
    assert data["role"] == "admin"


async def test_me_missing_token_401(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_invalid_token_401(client: AsyncClient):
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


# ── change-password ───────────────────────────────────────────────────────


async def test_change_password_happy_204(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/auth/change-password",
        headers=admin_ctx["headers"],
        json={"oldPassword": admin_ctx["password"], "newPassword": "Noua_Parola_9876"},
    )
    assert resp.status_code == 204
    # verifică că login-ul cu parola nouă merge
    login = await client.post(
        "/api/auth/login",
        json={"email": admin_ctx["email"], "password": "Noua_Parola_9876"},
    )
    assert login.status_code == 200
    # parola veche nu mai merge
    old_login = await client.post(
        "/api/auth/login",
        json={"email": admin_ctx["email"], "password": admin_ctx["password"]},
    )
    assert old_login.status_code == 401


async def test_change_password_invalid_old_400(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/auth/change-password",
        headers=admin_ctx["headers"],
        json={"oldPassword": "wrongwrongwrong", "newPassword": "Noua_Parola_9876"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_password"


async def test_change_password_same_400(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/auth/change-password",
        headers=admin_ctx["headers"],
        json={
            "oldPassword": admin_ctx["password"],
            "newPassword": admin_ctx["password"],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "same_password"


async def test_change_password_unauthenticated_401(client: AsyncClient):
    resp = await client.post(
        "/api/auth/change-password",
        json={"oldPassword": "Parola_Test_1234", "newPassword": "Noua_Parola_9876"},
    )
    assert resp.status_code == 401
