from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from fastapi import Request

from app.modules.audit import service as audit_service
from app.modules.auth import service as auth_service
from app.modules.auth.deps import get_current_admin, get_current_tenant_id
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import CreateUserRequest, UpdateUserRequest, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    users = await users_service.list_by_tenant(session, tenant_id)
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    payload: CreateUserRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    # Validare parolă — admin-ul nu poate seta parolă slabă pentru alt user.
    from app.core.security import validate_password_strength
    weak = validate_password_strength(payload.password)
    if weak:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "weak_password", "message": weak},
        )

    # Email e global unique în schema actuală — verificăm explicit pentru UX mai clar
    existing = await users_service.get_by_email(session, payload.email)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "email_taken", "message": "Există deja un user cu acest email"},
        )
    try:
        user = await users_service.create_user(
            session,
            tenant_id=admin.tenant_id,
            email=payload.email,
            password=payload.password,
            role=payload.role,
        )
        await auth_service.issue_email_verification(session, user)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "email_taken", "message": "Există deja un user cu acest email"},
        )
    await audit_service.log_event(
        session,
        event_type="user.created",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "role": user.role},
        request=request,
    )
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    request: Request,
    user_id: UUID,
    payload: UpdateUserRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await users_service.get_by_id(session, user_id)
    if target is None or target.tenant_id != admin.tenant_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Utilizator inexistent"},
        )
    # Siguranță: adminul nu se poate dezactiva pe sine (să rămână măcar un admin activ)
    if target.id == admin.id and payload.active is False:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "cannot_deactivate_self", "message": "Nu te poți dezactiva pe tine"},
        )
    changes: dict = {}
    if payload.role is not None and payload.role != target.role:
        changes["role"] = {"from": target.role, "to": payload.role}
    if payload.active is not None and payload.active != target.active:
        changes["active"] = {"from": target.active, "to": payload.active}

    updated = await users_service.update_user(
        session, target, role=payload.role, active=payload.active
    )
    if changes:
        await audit_service.log_event(
            session,
            event_type="user.updated",
            tenant_id=admin.tenant_id,
            user_id=admin.id,
            target_type="user",
            target_id=target.id,
            metadata=changes,
            request=request,
        )
    return UserOut.model_validate(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    target = await users_service.get_by_id(session, user_id)
    if target is None or target.tenant_id != admin.tenant_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "Utilizator inexistent"},
        )
    if target.id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "cannot_delete_self", "message": "Nu te poți șterge pe tine"},
        )
    email = target.email
    await users_service.delete_user(session, target)
    await audit_service.log_event(
        session,
        event_type="user.deleted",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        target_type="user",
        target_id=user_id,
        metadata={"email": email},
        request=request,
    )
    return None


@router.post("/{user_id}/impersonate")
async def impersonate_user(
    request: Request,
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Admin primește un token scurt (30min) care identifică un alt user din
    același tenant. Token-ul poartă `imp` claim = ID-ul admin-ului care impersonează.
    Frontend afișează banner clar când e activ.
    """
    target = await users_service.get_by_id(session, user_id)
    if target is None or target.tenant_id != admin.tenant_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User inexistent"},
        )
    if target.id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "self_impersonation", "message": "Ești deja tu"},
        )
    from app.core.security import create_access_token
    access = create_access_token(
        subject=str(target.id),
        extra_claims={"tid": str(target.tenant_id), "imp": str(admin.id)},
        expire_minutes=30,
    )
    await audit_service.log_event(
        session,
        event_type="admin.impersonation_started",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        target_type="user",
        target_id=target.id,
        metadata={"admin_email": admin.email, "target_email": target.email},
        request=request,
    )
    return {"accessToken": access, "tokenType": "bearer", "impersonating": target.email}
