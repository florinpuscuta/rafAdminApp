"""Teste pentru POST /api/auth/invitations/bulk-import."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


def _csv(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode("utf-8")


async def test_bulk_invite_happy_path(client: AsyncClient, admin_ctx):
    content = _csv([
        "email,role",
        "alice@example.com,member",
        "bob@example.com,manager",
        "carol@example.com,admin",
    ])
    resp = await client.post(
        "/api/auth/invitations/bulk-import",
        headers=admin_ctx["headers"],
        files={"file": ("team.csv", content, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invited"] == 3
    assert body["skipped"] == 0
    assert body["errors"] == []


async def test_bulk_invite_without_header(client: AsyncClient, admin_ctx):
    content = _csv([
        "dan@example.com,member",
        "eve@example.com,viewer",
    ])
    resp = await client.post(
        "/api/auth/invitations/bulk-import",
        headers=admin_ctx["headers"],
        files={"file": ("team.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json()["invited"] == 2


async def test_bulk_invite_skips_duplicates(client: AsyncClient, admin_ctx):
    """Dubluri în CSV + email-ul adminului deja existent → skipped, nu eroare."""
    admin_email = admin_ctx["user"]["email"]
    content = _csv([
        "email,role",
        "frank@example.com,member",
        "frank@example.com,member",  # duplicat
        f"{admin_email},admin",       # deja user
    ])
    resp = await client.post(
        "/api/auth/invitations/bulk-import",
        headers=admin_ctx["headers"],
        files={"file": ("team.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["invited"] == 1
    assert body["skipped"] == 2


async def test_bulk_invite_reports_bad_rows(client: AsyncClient, admin_ctx):
    content = _csv([
        "email,role",
        "valid@example.com,member",
        "not-an-email,member",
        "george@example.com,boss",  # rol invalid
    ])
    resp = await client.post(
        "/api/auth/invitations/bulk-import",
        headers=admin_ctx["headers"],
        files={"file": ("team.csv", content, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["invited"] == 1
    assert len(body["errors"]) == 2
    assert any("email invalid" in e for e in body["errors"])
    assert any("rol invalid" in e for e in body["errors"])


async def test_bulk_invite_rejects_non_csv(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/auth/invitations/bulk-import",
        headers=admin_ctx["headers"],
        files={"file": ("team.xlsx", b"binary", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_format"


async def test_bulk_invite_requires_admin(client: AsyncClient):
    resp = await client.post(
        "/api/auth/invitations/bulk-import",
        files={"file": ("team.csv", b"email,role\nx@y.z,member\n", "text/csv")},
    )
    assert resp.status_code == 401
