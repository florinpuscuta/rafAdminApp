"""
Audit log service. Helperul `log_event` inserează un rând în `audit_logs`
fără commit — caller-ul face commit odată cu tranzacția sa. Astfel auditul
e atomic cu acțiunea: dacă acțiunea rollback, și audit-ul rollback.

Convenție event_type: `<domain>.<action>[.<result>]`
  auth.login.success / auth.login.failed / auth.logout
  auth.password_changed / auth.password_reset_requested / auth.password_reset_completed
  auth.email_verified
  user.created / user.role_changed
  tenant.created
  alias.store.created / alias.agent.created / alias.product.created
  sales.batch_imported / sales.batch_deleted
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


async def log_event(
    session: AsyncSession,
    *,
    event_type: str,
    tenant_id: UUID | None = None,
    user_id: UUID | None = None,
    target_type: str | None = None,
    target_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    ip = None
    ua = None
    if request is not None:
        ip = request.client.host if request.client else None
        ua_val = request.headers.get("user-agent")
        if ua_val:
            ua = ua_val[:500]

    session.add(
        AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            event_metadata=metadata,
            ip_address=ip,
            user_agent=ua,
        )
    )
    await session.commit()


def _build_filters(
    tenant_id: UUID,
    *,
    event_type: str | None = None,
    event_prefix: str | None = None,
    user_id: UUID | None = None,
    since: "datetime | None" = None,
    until: "datetime | None" = None,
) -> list:
    filters = [AuditLog.tenant_id == tenant_id]
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if event_prefix:
        filters.append(AuditLog.event_type.startswith(event_prefix))
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    if since is not None:
        filters.append(AuditLog.created_at >= since)
    if until is not None:
        filters.append(AuditLog.created_at < until)
    return filters


async def list_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    page: int = 1,
    page_size: int = 50,
    event_type: str | None = None,
    event_prefix: str | None = None,
    user_id: UUID | None = None,
    since: "datetime | None" = None,
    until: "datetime | None" = None,
) -> tuple[list[AuditLog], int]:
    page = max(1, page)
    page_size = max(1, min(page_size, 500))

    filters = _build_filters(
        tenant_id, event_type=event_type, event_prefix=event_prefix,
        user_id=user_id, since=since, until=until,
    )

    total = (
        await session.execute(select(func.count(AuditLog.id)).where(*filters))
    ).scalar_one()

    stmt = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, int(total)


async def list_all_filtered(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    event_type: str | None = None,
    event_prefix: str | None = None,
    user_id: UUID | None = None,
    since: "datetime | None" = None,
    until: "datetime | None" = None,
    limit: int = 10_000,
) -> list[AuditLog]:
    """Pentru export — plafon de siguranță 10k rânduri."""
    filters = _build_filters(
        tenant_id, event_type=event_type, event_prefix=event_prefix,
        user_id=user_id, since=since, until=until,
    )
    stmt = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_event_types(session: AsyncSession, tenant_id: UUID) -> list[str]:
    """Tipurile distincte de evenimente — pentru popularea dropdown-ului de filtru."""
    result = await session.execute(
        select(AuditLog.event_type)
        .where(AuditLog.tenant_id == tenant_id)
        .distinct()
        .order_by(AuditLog.event_type)
    )
    return [row[0] for row in result.all()]
