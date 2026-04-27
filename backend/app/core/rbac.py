"""
Role-Based Access Control granular pentru rafAdminApp.

Roluri canonice (vezi `app.modules.users.models.UserRole`):
- `admin`             — acces total (settings, users, api keys, audit etc.)
- `director`          — vede tot, modifică majoritatea (fără settings critice)
- `finance_manager`   — costuri, marja, evaluare, raportari finance
- `regional_manager`  — vânzări + parcurs + activitate pentru regiunea sa
- `sales_agent`       — DOAR /parcurs și /activitate proprie
- `viewer`            — read-only la dashboard / rapoarte

Pentru endpoint-uri admin-only foloseste `Depends(get_current_admin)` sau,
mai granular, `Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR))`.

Aplicare la nivel de modul-router (toate endpoint-urile dintr-un APIRouter):

    from app.modules.users.models import UserRole
    from app.core.rbac import require_roles

    router = APIRouter(
        prefix="/api/api-keys",
        dependencies=[Depends(require_roles(UserRole.ADMIN))],
    )

Fallback safe: pentru user-i care încă au DOAR `role` legacy (pre-migration),
verificarea cade pe `role` (admin/manager/member/viewer). Astfel sistemul
nu pică dacă `role_v2` n-a fost încă populat.
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status

from app.modules.auth.deps import get_current_user
from app.modules.users.models import User, UserRole

# Aliasuri pentru tier-uri uzuale.
ADMIN_ONLY = {UserRole.ADMIN}
ADMIN_OR_DIRECTOR = {UserRole.ADMIN, UserRole.DIRECTOR}
MANAGEMENT = {
    UserRole.ADMIN,
    UserRole.DIRECTOR,
    UserRole.FINANCE_MANAGER,
    UserRole.REGIONAL_MANAGER,
}
ALL_LOGGED_IN = set(UserRole)  # toate rolurile autentificate


# ── Mapare legacy → role_v2 ────────────────────────────────────────────────
# Pentru user-i care nu au încă `role_v2` populat, traducem `role` legacy.
_LEGACY_MAP: dict[str, UserRole] = {
    "admin": UserRole.ADMIN,
    "manager": UserRole.DIRECTOR,
    "member": UserRole.SALES_AGENT,
    "viewer": UserRole.VIEWER,
}


def effective_role(user: User) -> UserRole:
    """Întoarce rolul efectiv al user-ului.

    Reguli de precedență:
    1. `role` legacy = "admin" → ADMIN, indiferent de `role_v2`. Asta e
       backwards-compat: signup-ul vechi setează `role="admin"` dar lasă
       `role_v2` pe default VIEWER. Fără regula asta admin-ii reali ar
       părea viewer-i.
    2. `role_v2` explicit (ADMIN, DIRECTOR, FINANCE_MANAGER, etc.) — folosit.
       VIEWER e considerat default neutilizat dacă coexistă cu un `role`
       legacy diferit; vezi mai jos.
    3. Fallback: traducere `role` legacy → `UserRole`.
    """
    if (user.role or "").lower() == "admin":
        return UserRole.ADMIN
    if user.role_v2 is not None:
        if isinstance(user.role_v2, UserRole):
            v2 = user.role_v2
        else:
            try:
                v2 = UserRole(user.role_v2)
            except ValueError:
                v2 = None  # type: ignore[assignment]
        if v2 is not None and v2 != UserRole.VIEWER:
            return v2
    return _LEGACY_MAP.get((user.role or "").lower(), UserRole.VIEWER)


def has_any_role(user: User, allowed: set[UserRole] | tuple[UserRole, ...]) -> bool:
    """Verifică dacă user-ul are unul din rolurile permise."""
    return effective_role(user) in set(allowed)


def require_roles(*allowed: UserRole) -> Callable[[User], User]:
    """Dependency factory: returnează o dependency FastAPI care permite doar
    user-ii cu unul din `allowed`.

    Folosire pe router (toate rutele):

        router = APIRouter(
            prefix="/api/foo",
            dependencies=[Depends(require_roles(UserRole.ADMIN))],
        )

    Folosire pe endpoint individual:

        @router.get("/x")
        async def x(user: User = Depends(require_roles(UserRole.ADMIN))):
            ...
    """
    if not allowed:
        raise ValueError("require_roles() needs at least one role")
    allowed_set = set(allowed)

    async def _check(user: User = Depends(get_current_user)) -> User:
        if not has_any_role(user, allowed_set):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "insufficient_role",
                    "message": (
                        "Rolul tău nu permite această operațiune. "
                        f"Permise: {sorted(r.value for r in allowed_set)}"
                    ),
                },
            )
        return user

    return _check


# ── Capabilities (frontend nav filter) ─────────────────────────────────────
# Sursa de adevăr pentru ce vede fiecare rol în meniu. Returnată din
# `/api/auth/me/capabilities` ca să frontend-ul ascundă meniurile inaccesibile.

# `module_name` corespunde cu prefixurile / numele de feature din UI
# (ex: "users", "audit", "consolidat", "parcurs"). NU sunt path-uri API,
# ci identificatori logici.
_CAPS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: {"*"},  # tot
    UserRole.DIRECTOR: {
        "dashboard", "consolidat", "vz_la_zi", "analiza_pe_luni",
        "analiza_magazin", "analiza_magazin_dashboard", "comenzi_fara_ind",
        "top_produse", "marca_privata", "margine", "marja_lunara", "mortare",
        "targhet", "bonusari", "prognoza", "promotions", "evaluare_agenti",
        "agents", "stores", "products", "sales", "orders", "gallery",
        "rapoarte_word", "rapoarte_lunar", "monthly_report", "ai",
        "activitate", "parcurs", "probleme",
        "mkt_concurenta", "mkt_catalog", "mkt_facing", "mkt_panouri",
        "mkt_sika", "grupe_produse", "audit",
    },
    UserRole.FINANCE_MANAGER: {
        "dashboard", "consolidat", "vz_la_zi", "analiza_pe_luni",
        "comenzi_fara_ind", "top_produse", "marca_privata", "margine",
        "marja_lunara", "targhet", "bonusari", "evaluare_agenti",
        "rapoarte_lunar", "monthly_report", "ai",
        "agents", "stores", "products", "sales", "orders",
    },
    UserRole.REGIONAL_MANAGER: {
        "dashboard", "consolidat", "vz_la_zi", "analiza_pe_luni",
        "analiza_magazin", "top_produse", "targhet", "evaluare_agenti",
        "ai",
        "agents", "stores", "sales",
        "activitate", "parcurs", "probleme",
        "mkt_concurenta", "mkt_facing", "mkt_panouri",
    },
    UserRole.SALES_AGENT: {
        "dashboard", "parcurs", "activitate", "probleme",
        "mkt_concurenta", "mkt_facing", "mkt_panouri",
    },
    # VIEWER vede tot ce vede DIRECTOR — toate modulele non-admin (rapoarte,
    # analize, marketing, etc.). Restricția lui e că datele despre agenți sunt
    # mascate automat în UI prin PrivacyProvider (forțat la login pentru viewer).
    # Vedere fără identificarea agenților, util pentru audit / parteneri.
    UserRole.VIEWER: {
        "dashboard", "consolidat", "vz_la_zi", "analiza_pe_luni",
        "analiza_magazin", "analiza_magazin_dashboard", "comenzi_fara_ind",
        "top_produse", "marca_privata", "margine", "marja_lunara", "mortare",
        "targhet", "bonusari", "prognoza", "promotions", "evaluare_agenti",
        "agents", "stores", "products", "sales", "orders", "gallery",
        "rapoarte_word", "rapoarte_lunar", "monthly_report", "ai",
        "activitate", "parcurs", "probleme",
        "mkt_concurenta", "mkt_catalog", "mkt_facing", "mkt_panouri",
        "mkt_sika", "grupe_produse", "audit",
    },
}


def capabilities_for(role: UserRole) -> set[str]:
    """Module accesibile pentru rolul dat. ADMIN întoarce `{'*'}` = wildcard."""
    return _CAPS.get(role, set())


def can_access_module(role: UserRole, module_name: str) -> bool:
    caps = capabilities_for(role)
    return "*" in caps or module_name in caps
