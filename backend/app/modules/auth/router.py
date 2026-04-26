from uuid import UUID

from fastapi import Depends, HTTPException, Request, UploadFile, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.core.rate_limit import limiter
from app.core.schemas import APISchema
from app.modules.audit import service as audit_service
from app.modules.auth import service as auth_service
from app.modules.auth.deps import get_current_admin, get_current_user
from app.modules.auth.schemas import (
    AcceptInvitationRequest,
    AuthResponse,
    BulkInviteResponse,
    ChangePasswordRequest,
    ConfirmEmailVerifyRequest,
    ConfirmPasswordResetRequest,
    CreateInvitationRequest,
    InvitationOut,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RequestPasswordResetRequest,
    SignupRequest,
    TOTPCodeRequest,
    TOTPSetupResponse,
    TokenPair,
)
from app.modules.tenants.schemas import TenantOut
from app.modules.users.models import User
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_response(user, tenant, access: str, refresh: str) -> AuthResponse:
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
        tenant=TenantOut.model_validate(tenant),
    )


# Codurile de eroare care înseamnă "input invalid" → 400, nu 409. Conflicte
# de stare (email deja folosit, etc) rămân 409. Valori incorecte ale user-ului
# (parolă slabă, token expirat, TOTP invalid) primesc 400.
_BAD_REQUEST_CODES = {
    "weak_password", "invalid_password", "invalid_token", "invalid_invitation",
    "invalid_totp", "totp_required", "same_password", "tenant_not_found",
    "user_not_found", "user_inactive", "tenant_inactive", "account_locked",
}


def _http_exc_from_auth_error(err) -> HTTPException:
    """Convertește AuthError la HTTPException cu status code corect."""
    code = 400 if err.code in _BAD_REQUEST_CODES else 409
    return HTTPException(code, detail={"code": err.code, "message": err.message})


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def signup(
    request: Request,
    payload: SignupRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        user, tenant, access, refresh = await auth_service.signup(
            session,
            tenant_name=payload.tenant_name,
            email=payload.email,
            password=payload.password,
        )
    except auth_service.AuthError as err:
        raise _http_exc_from_auth_error(err)
    await audit_service.log_event(
        session,
        event_type="tenant.created",
        tenant_id=tenant.id,
        user_id=user.id,
        target_type="tenant",
        target_id=tenant.id,
        metadata={"email": user.email},
        request=request,
    )
    return _auth_response(user, tenant, access, refresh)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("15/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        user, tenant, access, refresh = await auth_service.login(
            session,
            email=payload.email,
            password=payload.password,
            totp_code=payload.totp_code,
        )
    except auth_service.AuthError as err:
        await audit_service.log_event(
            session,
            event_type="auth.login.failed",
            metadata={"email": payload.email, "code": err.code},
            request=request,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": err.code, "message": err.message})
    await audit_service.log_event(
        session,
        event_type="auth.login.success",
        tenant_id=tenant.id,
        user_id=user.id,
        request=request,
    )
    return _auth_response(user, tenant, access, refresh)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


class CapabilitiesResponse(APISchema):
    role_v2: str
    modules: list[str]  # `["*"]` pentru admin (wildcard)


@router.get("/me/capabilities", response_model=CapabilitiesResponse)
async def my_capabilities(user: User = Depends(get_current_user)):
    """
    Capabilități pentru user-ul curent — folosit de frontend pentru a ascunde
    meniurile inaccesibile. Wildcard `["*"]` = toate modulele (admin).
    """
    from app.core.rbac import capabilities_for, effective_role

    role = effective_role(user)
    caps = capabilities_for(role)
    return CapabilitiesResponse(
        role_v2=role.value,
        modules=sorted(caps),
    )


from app.modules.tenants.models import Organization  # noqa: E402
from app.modules.users import service as users_service  # noqa: E402


class OrganizationMembershipOut(APISchema):
    organization_id: UUID
    name: str
    slug: str
    kind: str
    role_v2: str
    is_default: bool


class MembershipsResponse(APISchema):
    items: list[OrganizationMembershipOut] = Field(default_factory=list)


@router.get("/me/organizations", response_model=MembershipsResponse)
async def my_organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MembershipsResponse:
    """Listează organizațiile la care e membru user-ul curent.

    Frontend folosește răspunsul ca să afișeze switcher-ul "Adeplast / Sika /
    Sikadp" și trimite `X-Active-Org-Id` la următoarele request-uri.
    """
    memberships = await users_service.list_user_memberships(session, user.id)
    org_ids = [m.organization_id for m in memberships]
    if not org_ids:
        return MembershipsResponse(items=[])
    res = await session.execute(
        select(Organization).where(Organization.id.in_(org_ids))
    )
    org_by_id = {o.id: o for o in res.scalars().all()}
    items = []
    for m in memberships:
        org = org_by_id.get(m.organization_id)
        if org is None:
            continue
        items.append(OrganizationMembershipOut(
            organization_id=m.organization_id,
            name=org.name, slug=org.slug, kind=org.kind.value,
            role_v2=m.role_v2.value if hasattr(m.role_v2, "value") else m.role_v2,
            is_default=m.is_default,
        ))
    return MembershipsResponse(items=items)


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        _user, _tenant, access, refresh = await auth_service.rotate_refresh_token(
            session, refresh_token=payload.refresh_token
        )
    except auth_service.AuthError as err:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail={"code": err.code, "message": err.message},
        )
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    payload: LogoutRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # idempotent — nu 401/404, chiar dacă tokenul nu există
    await auth_service.revoke_refresh_token(session, refresh_token=payload.refresh_token)
    await audit_service.log_event(
        session,
        event_type="auth.logout",
        tenant_id=user.tenant_id,
        user_id=user.id,
        request=request,
    )
    return None


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def request_password_reset(
    request: Request,
    payload: RequestPasswordResetRequest,
    session: AsyncSession = Depends(get_session),
):
    await auth_service.request_password_reset(session, email=payload.email)
    await audit_service.log_event(
        session,
        event_type="auth.password_reset_requested",
        metadata={"email": payload.email},
        request=request,
    )
    # idempotent — răspuns identic indiferent dacă email-ul există
    return None


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: ConfirmPasswordResetRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        await auth_service.confirm_password_reset(
            session, token=payload.token, new_password=payload.new_password
        )
    except auth_service.AuthError as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": err.code, "message": err.message},
        )
    return None


@router.post("/email-verify/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email_verify(
    payload: ConfirmEmailVerifyRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        await auth_service.confirm_email_verification(session, token=payload.token)
    except auth_service.AuthError as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": err.code, "message": err.message},
        )
    return None


@router.post("/email-verify/resend", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def resend_email_verify(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await auth_service.resend_email_verification(session, user)
    return None


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await auth_service.change_password(
            session,
            user,
            old_password=payload.old_password,
            new_password=payload.new_password,
        )
    except auth_service.AuthError as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": err.code, "message": err.message},
        )
    await audit_service.log_event(
        session,
        event_type="auth.password_changed",
        tenant_id=user.tenant_id,
        user_id=user.id,
        request=request,
    )
    return None


# ── 2FA TOTP ─────────────────────────────────────────────────────────────


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def totp_setup(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Generează un secret TOTP nou + returnează provisioning_uri pentru QR.
    Secretul e salvat dar `totp_enabled` rămâne false până la /2fa/enable.
    """
    import pyotp
    from app.modules.users import service as users_service
    secret = pyotp.random_base32()
    await users_service.set_totp_secret(session, user, secret, enabled=False)
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="Adeplast SaaS"
    )
    return TOTPSetupResponse(secret=secret, provisioning_uri=uri)


@router.post("/2fa/enable", status_code=status.HTTP_204_NO_CONTENT)
async def totp_enable(
    request: Request,
    payload: TOTPCodeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import pyotp
    from app.modules.users import service as users_service
    if not user.totp_secret:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_secret", "message": "Rulează /2fa/setup întâi"},
        )
    if not pyotp.TOTP(user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_totp", "message": "Cod invalid"},
        )
    await users_service.set_totp_secret(session, user, user.totp_secret, enabled=True)
    await audit_service.log_event(
        session,
        event_type="auth.totp_enabled",
        tenant_id=user.tenant_id,
        user_id=user.id,
        request=request,
    )
    return None


@router.post("/2fa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def totp_disable(
    request: Request,
    payload: TOTPCodeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import pyotp
    from app.modules.users import service as users_service
    if not user.totp_enabled or not user.totp_secret:
        return None
    if not pyotp.TOTP(user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_totp", "message": "Cod invalid"},
        )
    # reset complet — șterge și secretul
    await users_service.set_totp_secret(session, user, None, enabled=False)  # type: ignore[arg-type]
    await audit_service.log_event(
        session,
        event_type="auth.totp_disabled",
        tenant_id=user.tenant_id,
        user_id=user.id,
        request=request,
    )
    return None


# ── Invitations ─────────────────────────────────────────────────────────


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    items = await auth_service.list_invitations(session, admin.tenant_id)
    return [InvitationOut.model_validate(i) for i in items]


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    request: Request,
    payload: CreateInvitationRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    from app.modules.users import service as users_service
    existing = await users_service.get_by_email(session, payload.email)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "email_taken", "message": "Există deja un user cu acest email"},
        )
    inv, _ = await auth_service.create_invitation(
        session,
        tenant_id=admin.tenant_id,
        email=payload.email,
        role=payload.role,
        invited_by_user_id=admin.id,
        inviter_email=admin.email,
    )
    await audit_service.log_event(
        session,
        event_type="invitation.created",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        target_type="invitation",
        target_id=inv.id,
        metadata={"email": payload.email, "role": payload.role},
        request=request,
    )
    return InvitationOut.model_validate(inv)


@router.post("/invitations/bulk-import", response_model=BulkInviteResponse)
async def bulk_import_invitations(
    request: Request,
    file: UploadFile,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Import bulk de invitații dintr-un CSV cu coloanele `email,role`.
    Linia 1 e header (opțional). Role-uri valide: admin, manager, member, viewer.
    Skip: email-uri deja active sau invitate anterior. Max 500 linii per batch.
    """
    import csv
    import io

    from app.modules.users import service as users_service

    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Se acceptă doar .csv"},
        )
    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fișier gol"},
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "bad_encoding", "message": "Fișierul trebuie să fie UTF-8"},
        )

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return BulkInviteResponse(invited=0, skipped=0, errors=["CSV gol"])

    # Detectăm header-ul (prima linie conține "email")
    start_idx = 0
    first_lower = [c.strip().lower() for c in rows[0]]
    if "email" in first_lower:
        email_col = first_lower.index("email")
        role_col = first_lower.index("role") if "role" in first_lower else 1
        start_idx = 1
    else:
        email_col = 0
        role_col = 1

    if len(rows) - start_idx > 500:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "too_many_rows", "message": "Max 500 linii per import"},
        )

    valid_roles = {"admin", "manager", "member", "viewer"}
    existing_users = {u.email.lower() for u in await users_service.list_by_tenant(session, admin.tenant_id)}
    existing_invites = {i.email.lower() for i in await auth_service.list_invitations(session, admin.tenant_id) if i.accepted_at is None}

    invited = 0
    skipped = 0
    errors: list[str] = []
    for line_no, row in enumerate(rows[start_idx:], start=start_idx + 1):
        if not row or all(c.strip() == "" for c in row):
            continue
        email = (row[email_col] if len(row) > email_col else "").strip().lower()
        role = (row[role_col] if len(row) > role_col else "member").strip().lower() or "member"
        if not email or "@" not in email:
            errors.append(f"Linia {line_no}: email invalid ('{email}')")
            continue
        if role not in valid_roles:
            errors.append(f"Linia {line_no}: rol invalid '{role}' — folosește {sorted(valid_roles)}")
            continue
        if email in existing_users or email in existing_invites:
            skipped += 1
            continue
        try:
            await auth_service.create_invitation(
                session,
                tenant_id=admin.tenant_id,
                email=email,
                role=role,
                invited_by_user_id=admin.id,
                inviter_email=admin.email,
            )
            existing_invites.add(email)
            invited += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Linia {line_no}: {exc}")

    await audit_service.log_event(
        session,
        event_type="invitation.bulk_imported",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        metadata={"filename": filename, "invited": invited, "skipped": skipped},
        request=request,
    )
    return BulkInviteResponse(invited=invited, skipped=skipped, errors=errors[:50])


@router.post("/invitations/accept", response_model=AuthResponse)
async def accept_invitation(
    request: Request,
    payload: AcceptInvitationRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        user, tenant, access, refresh = await auth_service.accept_invitation(
            session, token=payload.token, password=payload.password
        )
    except auth_service.AuthError as err:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": err.code, "message": err.message},
        )
    await audit_service.log_event(
        session,
        event_type="invitation.accepted",
        tenant_id=tenant.id,
        user_id=user.id,
        metadata={"email": user.email},
        request=request,
    )
    return _auth_response(user, tenant, access, refresh)
