"""
Scheduled cleanup — șterge token-urile expirate care nu mai servesc la nimic.

Fără cleanup, tabelele `refresh_tokens` / `email_verification_tokens` /
`password_reset_tokens` se umplu infinit (fiecare login = refresh token nou,
rotit etc). După luni de producție pot ajunge la milioane de rânduri, încetinind
indexările + crescând backup-urile.

Politica:
  - refresh_tokens: șterge cele cu `expires_at < now - GRACE_DAYS` SAU `revoked_at IS NOT NULL`
  - email_verification_tokens: șterge cele cu `used_at IS NOT NULL` SAU `expires_at < now`
  - password_reset_tokens: idem email verification
  - invitations expirate + neacceptate: șterge după 30 zile de expirare

Rulează într-o buclă asyncio în background (lifespan FastAPI), la fiecare
`CLEANUP_INTERVAL_HOURS`. În dev default e 24h; în prod poate fi setat prin env.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_

from app.core.db import SessionLocal
from app.modules.auth.models import (
    EmailVerificationToken,
    Invitation,
    PasswordResetToken,
    RefreshToken,
)

_log = logging.getLogger("adeplast.cleanup")

# Cât timp păstrăm refresh tokens expirate înainte să le ștergem. O mică
# fereastră de grație ajută la debug/audit ("când s-a expirat token-ul X?").
_REFRESH_GRACE_DAYS = 7
_INVITATION_GRACE_DAYS = 30


async def run_cleanup() -> dict[str, int]:
    """
    Rulează o pasă completă de cleanup. Returnează counts per tabelă.

    Sigur de apelat de mai multe ori — folosește `DELETE WHERE` idempotent.
    Poate fi apelat din endpoint admin, test, sau scheduler.
    """
    now = datetime.now(timezone.utc)
    counts: dict[str, int] = {}

    async with SessionLocal() as session:
        # Refresh tokens — revocate SAU expirate de mai mult de GRACE_DAYS
        grace_cutoff = now - timedelta(days=_REFRESH_GRACE_DAYS)
        res = await session.execute(
            delete(RefreshToken).where(
                or_(
                    RefreshToken.revoked_at.is_not(None),
                    RefreshToken.expires_at < grace_cutoff,
                )
            )
        )
        counts["refresh_tokens"] = res.rowcount or 0

        # Email verification tokens — folosite sau expirate
        res = await session.execute(
            delete(EmailVerificationToken).where(
                or_(
                    EmailVerificationToken.used_at.is_not(None),
                    EmailVerificationToken.expires_at < now,
                )
            )
        )
        counts["email_verification_tokens"] = res.rowcount or 0

        # Password reset tokens — folosite sau expirate
        res = await session.execute(
            delete(PasswordResetToken).where(
                or_(
                    PasswordResetToken.used_at.is_not(None),
                    PasswordResetToken.expires_at < now,
                )
            )
        )
        counts["password_reset_tokens"] = res.rowcount or 0

        # Invitații expirate + NEACCEPTATE de mai mult de 30 zile de la expirare.
        # Cele acceptate rămân ca istoric audit — nu le ștergem.
        inv_cutoff = now - timedelta(days=_INVITATION_GRACE_DAYS)
        res = await session.execute(
            delete(Invitation).where(
                Invitation.accepted_at.is_(None),
                Invitation.expires_at < inv_cutoff,
            )
        )
        counts["invitations"] = res.rowcount or 0

        await session.commit()

    total = sum(counts.values())
    if total > 0:
        _log.info("cleanup completed", extra={"counts": counts, "total": total})
    return counts


async def cleanup_scheduler(interval_hours: int = 24) -> None:
    """
    Loop infinit care rulează cleanup la fiecare `interval_hours`.
    Primul run se face după 5 minute de la startup (nu la boot, ca să nu
    încarce o pornire deja lentă).

    Oprit prin CancelledError când task-ul e cancel-uit la shutdown.
    """
    try:
        # Delay inițial ca să nu competiționăm cu migrații la boot
        await asyncio.sleep(300)
        while True:
            try:
                await run_cleanup()
            except Exception:  # noqa: BLE001
                _log.exception("cleanup run failed (continuing)")
            await asyncio.sleep(interval_hours * 3600)
    except asyncio.CancelledError:
        _log.info("cleanup scheduler cancelled (shutdown)")
        raise
