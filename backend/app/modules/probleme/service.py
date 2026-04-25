"""
Service "Probleme în Activitate" — citește și salvează din tabelul
`activity_problems` (upsert per tenant × scope × year × month).

Poze: integrarea cu modulul `gallery` este TODO (se va face în faza
următoare, când linkăm poze la (scope, year, month)).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.probleme.models import ActivityProblem

logger = logging.getLogger(__name__)


_MONTH_NAMES = {
    1: "Ianuarie", 2: "Februarie", 3: "Martie", 4: "Aprilie",
    5: "Mai", 6: "Iunie", 7: "Iulie", 8: "August",
    9: "Septembrie", 10: "Octombrie", 11: "Noiembrie", 12: "Decembrie",
}


def month_name(m: int) -> str:
    return _MONTH_NAMES.get(m, str(m))


def _to_dict(row: ActivityProblem | None, *, scope: str, year: int, month: int) -> dict[str, Any]:
    if row is None:
        return {
            "scope": scope,
            "year": year,
            "month": month,
            "month_name": month_name(month),
            "content": "",
            "updated_by": None,
            "updated_at": None,
            "photos": [],
            "todo": None,
        }
    return {
        "scope": row.scope,
        "year": row.year,
        "month": row.month,
        "month_name": month_name(row.month),
        "content": row.content,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at,
        "photos": [],
        "todo": None,
    }


async def get_probleme(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    year: int,
    month: int,
) -> dict[str, Any]:
    return await get_probleme_by_tenants(
        session, [tenant_id], scope=scope, year=year, month=month,
    )


async def get_probleme_by_tenants(
    session: AsyncSession,
    tenant_ids: list[UUID],
    *,
    scope: str,
    year: int,
    month: int,
) -> dict[str, Any]:
    """Multi-org: in SIKADP intoarce primul rand existent (toate orgele
    partajeaza aceeasi inregistrare logica per scope)."""
    if not tenant_ids:
        return _to_dict(None, scope=scope, year=year, month=month)
    row = (
        await session.execute(
            select(ActivityProblem).where(
                ActivityProblem.tenant_id.in_(tenant_ids),
                ActivityProblem.scope == scope,
                ActivityProblem.year == year,
                ActivityProblem.month == month,
            )
            .order_by(ActivityProblem.updated_at.desc().nulls_last())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _to_dict(row, scope=scope, year=year, month=month)


async def save_probleme(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    year: int,
    month: int,
    content: str,
    updated_by: str | None = None,
    updated_by_user_id: UUID | None = None,
) -> dict[str, Any]:
    existing = (
        await session.execute(
            select(ActivityProblem).where(
                ActivityProblem.tenant_id == tenant_id,
                ActivityProblem.scope == scope,
                ActivityProblem.year == year,
                ActivityProblem.month == month,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        row = ActivityProblem(
            tenant_id=tenant_id,
            scope=scope,
            year=year,
            month=month,
            content=content,
            updated_by=updated_by,
            updated_by_user_id=updated_by_user_id,
        )
        session.add(row)
    else:
        existing.content = content
        existing.updated_by = updated_by
        existing.updated_by_user_id = updated_by_user_id
        row = existing

    await session.commit()
    await session.refresh(row)
    logger.info(
        "probleme.save tenant=%s scope=%s %s/%s len=%d by=%s",
        tenant_id, scope, year, month, len(content), updated_by,
    )
    return _to_dict(row, scope=scope, year=year, month=month)
