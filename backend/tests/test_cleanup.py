"""Teste pentru run_cleanup — verifică reguli de expirare + idempotența."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.cleanup import run_cleanup
from app.core.db import SessionLocal
from app.modules.auth.models import (
    EmailVerificationToken,
    Invitation,
    PasswordResetToken,
    RefreshToken,
)


pytestmark = pytest.mark.asyncio


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def _get_user_id(client: AsyncClient) -> str:
    """Sign up un user fresh ca să avem un FK valid pentru tokens."""
    email = f"cleanup-{uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"tenantName": "Cleanup Inc", "email": email, "password": "Cleanup_Test_9876"},
    )
    assert resp.status_code == 201
    return resp.json()["user"]["id"]


async def test_deletes_expired_email_verification_tokens(client: AsyncClient):
    user_id = await _get_user_id(client)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as s:
        # Insert: 1 expirat, 1 valid
        s.add(EmailVerificationToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now - timedelta(days=1),
        ))
        s.add(EmailVerificationToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now + timedelta(days=1),
        ))
        await s.commit()

    counts = await run_cleanup()
    assert counts["email_verification_tokens"] >= 1

    async with SessionLocal() as s:
        remaining = (await s.execute(
            select(func.count()).select_from(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)
        )).scalar_one()
        # Signup creează 1 token valid automat + noi am adăugat 1 valid + 1 expirat.
        # După cleanup: cele 2 valide rămân, cel expirat e șters.
        assert remaining == 2


async def test_deletes_used_email_verification_tokens(client: AsyncClient):
    user_id = await _get_user_id(client)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as s:
        s.add(EmailVerificationToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now + timedelta(days=1),
            used_at=now,  # folosit deja
        ))
        await s.commit()

    await run_cleanup()

    async with SessionLocal() as s:
        remaining = (await s.execute(
            select(func.count()).select_from(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)
        )).scalar_one()
        # Signup creează 1 valid automat; cel cu used_at e șters → rămâne doar cel valid.
        assert remaining == 1


async def test_deletes_revoked_refresh_tokens(client: AsyncClient):
    user_id = await _get_user_id(client)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as s:
        # Revocat (logout explicit) — valid ca expirare dar revoked
        s.add(RefreshToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now + timedelta(days=30),
            revoked_at=now,
        ))
        # Valid neatins
        s.add(RefreshToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now + timedelta(days=30),
        ))
        await s.commit()

    await run_cleanup()

    async with SessionLocal() as s:
        remaining = (await s.execute(
            select(func.count()).select_from(RefreshToken)
            .where(RefreshToken.user_id == user_id)
        )).scalar_one()
        # Sign-up a creat 1 refresh token valid + noi am adăugat 1 valid + 1 revoked.
        # Rămân cele 2 valide.
        assert remaining == 2


async def test_keeps_expired_refresh_tokens_within_grace_period(client: AsyncClient):
    """Grace 7 zile: expirate DAR cu expires_at > now - 7d rămân (pt audit)."""
    user_id = await _get_user_id(client)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as s:
        # Expirat acum 3 zile — în grace, rămâne
        s.add(RefreshToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now - timedelta(days=3),
        ))
        # Expirat acum 10 zile — peste grace, șters
        s.add(RefreshToken(
            user_id=user_id, token_hash=_hash(secrets.token_hex(16)),
            expires_at=now - timedelta(days=10),
        ))
        await s.commit()

    await run_cleanup()

    async with SessionLocal() as s:
        remaining = (await s.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        )).scalars().all()
    # Sign-up creează 1 valid. Plus cele 2 → 3 intrări. După cleanup:
    # - sign-up valid rămâne
    # - 3 zile grace rămâne
    # - 10 zile peste grace → șters
    assert len(remaining) == 2


async def test_deletes_old_unaccepted_invitations(client: AsyncClient, admin_ctx):
    now = datetime.now(timezone.utc)

    async with SessionLocal() as s:
        # Expirată acum 40 zile, neacceptată → peste grace 30 zile, șters
        s.add(Invitation(
            tenant_id=admin_ctx["tenant"]["id"],
            email="old-inv@example.com",
            role="member",
            token_hash=_hash(secrets.token_hex(16)),
            expires_at=now - timedelta(days=40),
        ))
        # Expirată acum 10 zile, neacceptată → în grace, rămâne
        s.add(Invitation(
            tenant_id=admin_ctx["tenant"]["id"],
            email="recent-inv@example.com",
            role="member",
            token_hash=_hash(secrets.token_hex(16)),
            expires_at=now - timedelta(days=10),
        ))
        # Expirată acum 50 zile DAR acceptată → rămâne (istoric audit)
        s.add(Invitation(
            tenant_id=admin_ctx["tenant"]["id"],
            email="accepted-inv@example.com",
            role="member",
            token_hash=_hash(secrets.token_hex(16)),
            expires_at=now - timedelta(days=50),
            accepted_at=now - timedelta(days=45),
        ))
        await s.commit()

    await run_cleanup()

    async with SessionLocal() as s:
        emails_left = {
            i.email for i in (await s.execute(
                select(Invitation).where(Invitation.tenant_id == admin_ctx["tenant"]["id"])
            )).scalars()
        }
    assert "recent-inv@example.com" in emails_left
    assert "accepted-inv@example.com" in emails_left
    assert "old-inv@example.com" not in emails_left


async def test_cleanup_is_idempotent(client: AsyncClient):
    """A doua apelare imediată nu ar trebui să mai șteargă nimic."""
    await _get_user_id(client)

    first = await run_cleanup()
    second = await run_cleanup()
    # Al doilea run are toate 0
    assert sum(second.values()) == 0, f"Second run still deleted: {second}"
    # Primul poate avea 0 (fresh DB) sau >0 dacă ceva a fost deja expirat
    assert all(v >= 0 for v in first.values())
