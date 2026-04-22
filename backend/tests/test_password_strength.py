"""Teste pentru validate_password_strength + integrare în endpoint-uri."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security import validate_password_strength


pytestmark = pytest.mark.asyncio


# ── Unit tests pentru validator ─────────────────────────────────────────────


def test_too_short():
    assert validate_password_strength("abc") is not None


def test_all_same_char_rejected():
    assert validate_password_strength("aaaaaaaa") is not None


def test_single_class_rejected_even_if_long():
    assert validate_password_strength("abcdefghijkl") is not None  # doar lower
    assert validate_password_strength("123456789012") is not None  # doar digit


def test_weak_prefix_rejected_with_trivial_suffix():
    """Prefix comun + suffix format doar din cifre/simboluri → respins."""
    assert validate_password_strength("password123") is not None
    assert validate_password_strength("Parola2024!") is not None
    assert validate_password_strength("qwerty123!") is not None
    assert validate_password_strength("admin1234") is not None
    assert validate_password_strength("parola1234") is not None


def test_weak_prefix_accepted_when_suffix_has_letters():
    """Prefix comun + litere în suffix NU e predictible → acceptat."""
    assert validate_password_strength("Parola_Test_1234") is None
    assert validate_password_strength("PasswordIsReallyLong!") is None


def test_strong_password_accepted():
    assert validate_password_strength("MyStr0ng!Pwd") is None
    assert validate_password_strength("Unica7fraza") is None  # lower+upper+digit
    assert validate_password_strength("adeplast2026") is None  # lower+digit


# ── Integration tests ──────────────────────────────────────────────────────


async def test_signup_rejects_weak_password(client: AsyncClient):
    email = f"weak-{uuid4().hex[:6]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Acme", "email": email, "password": "aaaaaaaa"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "weak_password"


async def test_signup_rejects_common_prefix(client: AsyncClient):
    email = f"common-{uuid4().hex[:6]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Acme", "email": email, "password": "password123"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "weak_password"


async def test_signup_accepts_strong_password(client: AsyncClient):
    email = f"strong-{uuid4().hex[:6]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Acme", "email": email, "password": "MyStr0ng!Pwd"},
    )
    assert resp.status_code == 201


async def test_admin_create_user_rejects_weak_password(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/users",
        headers=admin_ctx["headers"],
        json={
            "email": f"member-{uuid4().hex[:6]}@example.com",
            "password": "aaaaaaaa",
            "role": "member",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "weak_password"


async def test_change_password_rejects_weak(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/auth/change-password",
        headers=admin_ctx["headers"],
        json={"oldPassword": "Parola_Test_1234", "newPassword": "aaaaaaaa"},
    )
    # 400 cu code=weak_password
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "weak_password"
