import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import (
    send_email_verification_email,
    send_invitation_email,
    send_password_reset_email,
)
from app.core.security import create_access_token, validate_password_strength, verify_password
from app.modules.auth.models import (
    EmailVerificationToken,
    Invitation,
    PasswordResetToken,
    RefreshToken,
)
from app.modules.tenants import service as tenants_service
from app.modules.tenants.models import Tenant
from app.modules.users import service as users_service
from app.modules.users.models import User


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _issue_refresh_token(session: AsyncSession, user_id) -> str:
    """Generează un refresh token nou (returnează raw), adaugă în sesiune (fără commit)."""
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    session.add(
        RefreshToken(
            user_id=user_id, token_hash=_hash_token(raw), expires_at=expires_at
        )
    )
    return raw


async def rotate_refresh_token(
    session: AsyncSession, *, refresh_token: str
) -> tuple[User, Tenant, str, str]:
    """
    Validează refresh token, îl marchează `used_at`, emite pereche nouă.
    Returnează (user, tenant, new_access, new_refresh).
    Aruncă AuthError pentru token invalid / expirat / deja folosit / revocat.
    """
    token_hash = _hash_token(refresh_token)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    tok = result.scalar_one_or_none()
    if tok is None:
        raise AuthError("invalid_token", "Refresh token invalid")
    if tok.used_at is not None or tok.revoked_at is not None or tok.expires_at <= now:
        raise AuthError("invalid_token", "Refresh token expirat sau invalidat")

    user = await users_service.get_by_id(session, tok.user_id)
    if user is None or not user.active:
        raise AuthError("user_inactive", "Cont inactiv")

    tenant = await session.get(Tenant, user.tenant_id)
    if tenant is None or not tenant.active:
        raise AuthError("tenant_inactive", "Organizația este dezactivată")

    tok.used_at = now
    new_refresh = await _issue_refresh_token(session, user.id)
    await session.commit()

    new_access = create_access_token(
        subject=str(user.id), extra_claims={"tid": str(tenant.id)}
    )
    return user, tenant, new_access, new_refresh


async def create_invitation(
    session: AsyncSession,
    *,
    tenant_id,
    email: str,
    role: str,
    invited_by_user_id,
    inviter_email: str,
) -> tuple[Invitation, str]:
    """Generează invitație cu token raw; log/email link-ul. Returnează (row, raw_token)."""
    raw = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    inv = Invitation(
        tenant_id=tenant_id,
        email=email.lower().strip(),
        role=role,
        token_hash=_hash_token(raw),
        invited_by_user_id=invited_by_user_id,
        expires_at=expires_at,
    )
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    invite_url = f"{settings.frontend_url}/accept-invite?token={raw}"
    await send_invitation_email(to_email=email, invite_url=invite_url, inviter_email=inviter_email)
    return inv, raw


async def list_invitations(session: AsyncSession, tenant_id) -> list[Invitation]:
    result = await session.execute(
        select(Invitation)
        .where(Invitation.tenant_id == tenant_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())


async def accept_invitation(
    session: AsyncSession, *, token: str, password: str
) -> tuple[User, Tenant, str, str]:
    """Acceptă invitație: creează user + marchează invitația acceptată + login."""
    weak = validate_password_strength(password)
    if weak:
        raise AuthError("weak_password", weak)

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Invitation).where(Invitation.token_hash == token_hash)
    )
    inv = result.scalar_one_or_none()
    if inv is None or inv.accepted_at is not None or inv.expires_at <= now:
        raise AuthError("invalid_invitation", "Invitație invalidă sau expirată")

    existing = await users_service.get_by_email(session, inv.email)
    if existing is not None:
        raise AuthError("email_taken", "Există deja un user cu acest email")

    user = await users_service.create_user(
        session,
        tenant_id=inv.tenant_id,
        email=inv.email,
        password=password,
        role=inv.role,
    )
    # email-ul e considerat verificat (a venit prin link valid)
    user.email_verified = True
    user.email_verified_at = now
    inv.accepted_at = now
    refresh_raw = await _issue_refresh_token(session, user.id)
    await session.commit()

    tenant = await session.get(Tenant, inv.tenant_id)
    if tenant is None:
        raise AuthError("tenant_not_found", "Organizația nu mai există")

    access = create_access_token(subject=str(user.id), extra_claims={"tid": str(tenant.id)})
    return user, tenant, access, refresh_raw


async def revoke_refresh_token(session: AsyncSession, *, refresh_token: str) -> None:
    """Idempotent — dacă tokenul nu există sau e deja revocat, nu eroare."""
    token_hash = _hash_token(refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    tok = result.scalar_one_or_none()
    if tok is not None and tok.revoked_at is None:
        tok.revoked_at = datetime.now(timezone.utc)
        await session.commit()


async def issue_email_verification(session: AsyncSession, user: User) -> None:
    """
    Generează un token de verificare email + trimite email-ul (dev: log).
    Se apelează după create user (signup sau admin create).
    Notă: NU commit — caller commite tranzacția.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=settings.email_verify_expire_hours
    )
    session.add(
        EmailVerificationToken(
            user_id=user.id, token_hash=token_hash, expires_at=expires_at
        )
    )
    verify_url = f"{settings.frontend_url}/verify-email?token={raw_token}"
    await send_email_verification_email(to_email=user.email, verify_url=verify_url)


async def confirm_email_verification(session: AsyncSession, *, token: str) -> None:
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    tok = result.scalar_one_or_none()
    if tok is None or tok.used_at is not None or tok.expires_at <= now:
        raise AuthError("invalid_token", "Token invalid sau expirat")

    user = await users_service.get_by_id(session, tok.user_id)
    if user is None:
        raise AuthError("user_not_found", "Utilizatorul nu mai există")

    user.email_verified = True
    user.email_verified_at = now
    tok.used_at = now
    await session.commit()


async def resend_email_verification(session: AsyncSession, user: User) -> None:
    if user.email_verified:
        return  # no-op dacă e deja verificat
    await issue_email_verification(session, user)
    await session.commit()


async def request_password_reset(session: AsyncSession, *, email: str) -> None:
    """
    Generează un token de reset. Răspunsul e idempotent (același behavior
    indiferent dacă email-ul există sau nu) ca să prevenim enumeration attacks.
    Token-ul RAW e trimis pe email (abstractizat), iar HASH-ul e stocat în DB.
    """
    user = await users_service.get_by_email(session, email)
    if user is None or not user.active:
        return  # idempotent: nu leak-uim că email-ul nu există

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_expire_minutes
    )

    reset = PasswordResetToken(
        user_id=user.id, token_hash=token_hash, expires_at=expires_at
    )
    session.add(reset)
    await session.commit()

    reset_url = f"{settings.frontend_url}/reset-password?token={raw_token}"
    await send_password_reset_email(to_email=user.email, reset_url=reset_url)


async def confirm_password_reset(
    session: AsyncSession, *, token: str, new_password: str
) -> None:
    weak = validate_password_strength(new_password)
    if weak:
        raise AuthError("weak_password", weak)

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    reset = result.scalar_one_or_none()
    if (
        reset is None
        or reset.used_at is not None
        or reset.expires_at <= now
    ):
        raise AuthError("invalid_token", "Token invalid sau expirat")

    user = await users_service.get_by_id(session, reset.user_id)
    if user is None or not user.active:
        raise AuthError("user_not_found", "Utilizatorul nu mai există")

    await users_service.update_password(session, user, new_password)
    reset.used_at = now
    await session.commit()


class AuthError(Exception):
    """Ridicată pentru orice eroare de auth (conflict email, credențiale invalide etc.)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def signup(
    session: AsyncSession,
    *,
    tenant_name: str,
    email: str,
    password: str,
) -> tuple[User, Tenant, str]:
    weak = validate_password_strength(password)
    if weak:
        raise AuthError("weak_password", weak)

    existing = await users_service.get_by_email(session, email)
    if existing is not None:
        raise AuthError("email_taken", "Email-ul este deja înregistrat")

    tenant = await tenants_service.create_tenant(session, name=tenant_name)
    user = await users_service.create_user(
        session,
        tenant_id=tenant.id,
        email=email,
        password=password,
        role="admin",
    )
    await issue_email_verification(session, user)
    refresh_raw = await _issue_refresh_token(session, user.id)
    await session.commit()
    await session.refresh(tenant)
    await session.refresh(user)

    access = create_access_token(subject=str(user.id), extra_claims={"tid": str(tenant.id)})
    return user, tenant, access, refresh_raw


async def change_password(
    session: AsyncSession, user: User, *, old_password: str, new_password: str
) -> None:
    if not verify_password(old_password, user.password_hash):
        raise AuthError("invalid_password", "Parola veche este incorectă")
    if old_password == new_password:
        raise AuthError("same_password", "Parola nouă trebuie să fie diferită de cea veche")
    weak = validate_password_strength(new_password)
    if weak:
        raise AuthError("weak_password", weak)
    await users_service.update_password(session, user, new_password)
    await session.commit()


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    totp_code: str | None = None,
) -> tuple[User, Tenant, str]:
    user = await users_service.get_by_email(session, email)
    if user is None:
        # nu leak-uim existența — același mesaj ca parolă greșită
        raise AuthError("invalid_credentials", "Email sau parolă incorectă")

    # 1. verifică lock
    now = datetime.now(timezone.utc)
    if user.locked_until is not None and user.locked_until > now:
        mins = max(1, int((user.locked_until - now).total_seconds() / 60))
        raise AuthError(
            "account_locked",
            f"Contul e blocat temporar. Reîncearcă în ~{mins} min.",
        )

    # 2. verifică parola
    if not verify_password(password, user.password_hash):
        await users_service.record_failed_login(
            session,
            user,
            max_attempts=settings.failed_login_max_attempts,
            lock_minutes=settings.failed_login_lock_minutes,
        )
        raise AuthError("invalid_credentials", "Email sau parolă incorectă")

    if not user.active:
        raise AuthError("user_inactive", "Contul este dezactivat")

    # 2.5 — 2FA check (după parolă)
    if user.totp_enabled and user.totp_secret:
        import pyotp
        if not totp_code:
            raise AuthError("totp_required", "Cod 2FA necesar")
        if not pyotp.TOTP(user.totp_secret).verify(totp_code, valid_window=1):
            raise AuthError("invalid_totp", "Cod 2FA invalid")

    # 3. succes — reset contor + update last_login
    await users_service.reset_failed_login(session, user)
    await users_service.touch_last_login(session, user)

    tenant_result = await session.get(Tenant, user.tenant_id)
    if tenant_result is None or not tenant_result.active:
        raise AuthError("tenant_inactive", "Organizația este dezactivată")

    refresh_raw = await _issue_refresh_token(session, user.id)
    await session.commit()
    await session.refresh(user)

    access = create_access_token(subject=str(user.id), extra_claims={"tid": str(tenant_result.id)})
    return user, tenant_result, access, refresh_raw
