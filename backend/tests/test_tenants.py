"""Teste pentru modulul tenants: structura tenantului creat la signup,
slug auto-generation și unicitate slug-uri.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_signup_creates_tenant_with_admin_user(client: AsyncClient):
    email = f"owner-{uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Widgets Inc", "email": email, "password": "Parola_Test_1234"},
    )
    assert resp.status_code == 201
    data = resp.json()
    # tenant creat
    assert data["tenant"]["name"] == "Widgets Inc"
    assert data["tenant"]["slug"] == "widgets-inc"
    assert data["tenant"]["active"] is True
    # user e admin + linked la tenant
    assert data["user"]["role"] == "admin"
    assert data["user"]["tenantId"] == data["tenant"]["id"]


async def test_slug_generated_from_tenant_name(client: AsyncClient):
    resp = await client.post(
        "/api/auth/signup",
        json={
            "tenantName": "  ACME  RO S.A.  ",
            "email": f"a-{uuid4().hex[:8]}@example.com",
            "password": "Parola_Test_1234",
        },
    )
    assert resp.status_code == 201
    slug = resp.json()["tenant"]["slug"]
    # non-alfanumerice → "-", trim leading/trailing
    assert slug.startswith("acme")
    assert " " not in slug
    assert "." not in slug


async def test_duplicate_tenant_name_generates_unique_slug(client: AsyncClient):
    """Doi signup-uri cu același nume de tenant → slug-uri diferite
    (primul "adeplast", al doilea "adeplast-2").
    """
    r1 = await client.post(
        "/api/auth/signup",
        json={
            "tenantName": "Adeplast",
            "email": f"first-{uuid4().hex[:8]}@example.com",
            "password": "Parola_Test_1234",
        },
    )
    r2 = await client.post(
        "/api/auth/signup",
        json={
            "tenantName": "Adeplast",
            "email": f"second-{uuid4().hex[:8]}@example.com",
            "password": "Parola_Test_1234",
        },
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    slug1 = r1.json()["tenant"]["slug"]
    slug2 = r2.json()["tenant"]["slug"]
    assert slug1 == "adeplast"
    assert slug2 == "adeplast-2"
    assert slug1 != slug2


async def test_tenant_ids_are_unique(client: AsyncClient):
    r1 = await client.post(
        "/api/auth/signup",
        json={
            "tenantName": "Alpha",
            "email": f"a-{uuid4().hex[:8]}@example.com",
            "password": "Parola_Test_1234",
        },
    )
    r2 = await client.post(
        "/api/auth/signup",
        json={
            "tenantName": "Beta",
            "email": f"b-{uuid4().hex[:8]}@example.com",
            "password": "Parola_Test_1234",
        },
    )
    assert r1.json()["tenant"]["id"] != r2.json()["tenant"]["id"]
