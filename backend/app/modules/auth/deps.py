"""
FastAPI dependencies pentru auth și tenant scoping.

Convenție: orice endpoint care atinge date tenant-scoped trebuie să accepte
`tenant_id = Depends(get_current_tenant_id)` și să transmită ID-ul către
service; service-ul trebuie să filtreze explicit după `tenant_id`.
Nu ne bazăm pe "magic" — izolarea e vizibilă în cod, nu ascunsă în middleware.
"""
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.logging import bind_request_context
from app.core.security import decode_access_token
from app.modules.users import service as users_service
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)


async def _decode_or_401(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    # Alternativă: autentificare via X-API-Key (pentru access programatic)
    api_key_header = request.headers.get("x-api-key")
    if api_key_header and credentials is None:
        from app.modules.api_keys import service as api_keys_service
        key = await api_keys_service.authenticate(session, api_key_header)
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        # Folosim user-ul creator al key-ului ca identitate; dacă a fost șters,
        # încercăm orice alt admin al tenantului (rar, dar posibil).
        if key.created_by_user_id:
            user = await users_service.get_by_id(session, key.created_by_user_id)
            if user is not None and user.active and user.tenant_id == key.tenant_id:
                bind_request_context(user_id=str(user.id), tenant_id=str(user.tenant_id))
                return user
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key creator inactive")

    # Flow normal: Bearer JWT
    payload = await _decode_or_401(credentials)

    sub = payload.get("sub")
    tid = payload.get("tid")
    if not sub or not tid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")

    try:
        user_id = UUID(sub)
        token_tenant_id = UUID(tid)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token ids")

    user = await users_service.get_by_id(session, user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    # token invalidat dacă user-ul a fost mutat între tenanti (edge-case)
    if user.tenant_id != token_tenant_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token/tenant mismatch")

    bind_request_context(user_id=str(user.id), tenant_id=str(user.tenant_id))
    return user


_ORG_ALL_SENTINEL = "all"


async def get_current_org_ids(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[UUID]:
    """Returneaza lista de organization_id-uri ACTIVE pentru request-ul curent.

    Logica:
      1. Header `X-Active-Org-Id: all` → toate org-urile user-ului (consolidated).
      2. Header `X-Active-Org-Id: <UUID>` → o singura orga (validata membership).
      3. Fara header → [user.tenant_id] (orga default).
    """
    requested = request.headers.get("x-active-org-id")
    if not requested:
        return [user.tenant_id]
    if requested.lower() == _ORG_ALL_SENTINEL:
        memberships = await users_service.list_user_memberships(session, user.id)
        ids = [m.organization_id for m in memberships]
        if not ids:
            ids = [user.tenant_id]
        return ids
    try:
        requested_id = UUID(requested)
    except ValueError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_org_id", "message": "X-Active-Org-Id invalid"},
        )
    if requested_id == user.tenant_id:
        return [requested_id]
    if not await users_service.is_member(session, user.id, requested_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "not_member",
                "message": "Nu esti membru al acestei organizatii",
            },
        )
    bind_request_context(user_id=str(user.id), tenant_id=str(requested_id))
    return [requested_id]


async def get_current_tenant_id(
    user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
) -> UUID:
    """Single-org dep — pentru endpoint-uri care NU suporta consolidated view.

    Cand user-ul trimite `X-Active-Org-Id: all` (sikadp consolidated mode),
    facem fallback silent la `users.tenant_id` (orga default). Endpoint-ul
    afiseaza date dintr-o singura orga; frontend-ul arata banner indicator
    ca vederea NU e consolidata.
    """
    if len(org_ids) != 1:
        return user.tenant_id
    return org_ids[0]


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency pentru endpoint-uri restrânse la admini (create users, etc).

    Acceptă DOAR rolul de admin — verifică atât `role` legacy cât și `role_v2`
    (canonic). User-i fără `role_v2` setat folosesc fallback pe `role`.
    """
    # Lazy import ca să evităm cicluri.
    from app.core.rbac import effective_role
    from app.modules.users.models import UserRole

    if effective_role(user) != UserRole.ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "not_admin", "message": "Operațiune permisă doar adminilor"},
        )
    return user
