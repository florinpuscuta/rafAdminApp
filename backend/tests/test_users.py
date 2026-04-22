"""Teste pentru modulul users: list scoped la tenant, create (admin-only),
duplicate email conflict.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_list_users_returns_only_owner_initially(
    client: AsyncClient, admin_ctx
):
    resp = await client.get("/api/users", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 1
    assert users[0]["email"] == admin_ctx["email"]
    assert users[0]["role"] == "admin"


async def test_admin_can_create_user_201(client: AsyncClient, admin_ctx):
    new_email = f"member-{uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/users",
        headers=admin_ctx["headers"],
        json={"email": new_email, "password": "Parola_Test_1234", "role": "member"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == new_email
    assert data["role"] == "member"
    # același tenant ca admin-ul
    assert data["tenantId"] == admin_ctx["tenant"]["id"]

    # listarea reflectă user-ul nou
    lst = await client.get("/api/users", headers=admin_ctx["headers"])
    assert lst.status_code == 200
    assert len(lst.json()) == 2


async def test_non_admin_cannot_create_user_403(client: AsyncClient, admin_ctx):
    # admin creează un member
    member_email = f"member-{uuid4().hex[:8]}@example.com"
    create = await client.post(
        "/api/users",
        headers=admin_ctx["headers"],
        json={"email": member_email, "password": "Parola_Test_1234", "role": "member"},
    )
    assert create.status_code == 201

    # member login → primește token de non-admin
    login = await client.post(
        "/api/auth/login",
        json={"email": member_email, "password": "Parola_Test_1234"},
    )
    assert login.status_code == 200
    member_token = login.json()["accessToken"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # member încearcă să creeze user → 403
    resp = await client.post(
        "/api/users",
        headers=member_headers,
        json={
            "email": f"forbidden-{uuid4().hex[:8]}@example.com",
            "password": "Parola_Test_1234",
            "role": "member",
        },
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "not_admin"


async def test_create_user_duplicate_email_409(client: AsyncClient, admin_ctx):
    email = f"dup-{uuid4().hex[:8]}@example.com"
    first = await client.post(
        "/api/users",
        headers=admin_ctx["headers"],
        json={"email": email, "password": "Parola_Test_1234", "role": "member"},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/users",
        headers=admin_ctx["headers"],
        json={"email": email, "password": "alteparola123", "role": "member"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "email_taken"


async def test_list_users_scoped_to_tenant(client: AsyncClient, signup_user):
    """user A (tenant A) vede doar user-ii tenantului A, nu și ai tenantului B."""
    a = await signup_user(tenant_name="Tenant A")
    b = await signup_user(tenant_name="Tenant B")

    # admin A creează un member în tenant A
    extra_email = f"extra-{uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/users",
        headers=a["headers"],
        json={"email": extra_email, "password": "Parola_Test_1234", "role": "member"},
    )

    # listarea pe headers A → 2 (owner + extra)
    list_a = await client.get("/api/users", headers=a["headers"])
    assert list_a.status_code == 200
    emails_a = {u["email"] for u in list_a.json()}
    assert a["email"] in emails_a
    assert extra_email in emails_a
    assert b["email"] not in emails_a

    # listarea pe headers B → doar owner B
    list_b = await client.get("/api/users", headers=b["headers"])
    assert list_b.status_code == 200
    emails_b = {u["email"] for u in list_b.json()}
    assert emails_b == {b["email"]}


async def test_list_users_requires_auth(client: AsyncClient):
    resp = await client.get("/api/users")
    assert resp.status_code == 401
