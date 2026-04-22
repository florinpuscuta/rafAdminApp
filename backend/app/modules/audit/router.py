import csv
import io
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.audit.schemas import AuditLogListResponse, AuditLogOut
from app.modules.auth.deps import get_current_admin
from app.modules.users.models import User

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    # Acceptăm ISO-8601 (cu sau fără timezone). Date-only (YYYY-MM-DD) → midnight UTC.
    try:
        if len(value) == 10:
            dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500, alias="pageSize"),
    event_type: str | None = Query(None, alias="eventType"),
    event_prefix: str | None = Query(None, alias="eventPrefix"),
    user_id: UUID | None = Query(None, alias="userId"),
    since: str | None = Query(None),
    until: str | None = Query(None),
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    items, total = await audit_service.list_for_tenant(
        session,
        admin.tenant_id,
        page=page,
        page_size=page_size,
        event_type=event_type,
        event_prefix=event_prefix,
        user_id=user_id,
        since=_parse_dt(since),
        until=_parse_dt(until),
    )
    return AuditLogListResponse(
        items=[AuditLogOut.model_validate(it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/event-types", response_model=list[str])
async def list_event_types(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    return await audit_service.list_event_types(session, admin.tenant_id)


@router.get("/export")
async def export_audit_logs(
    event_type: str | None = Query(None, alias="eventType"),
    event_prefix: str | None = Query(None, alias="eventPrefix"),
    user_id: UUID | None = Query(None, alias="userId"),
    since: str | None = Query(None),
    until: str | None = Query(None),
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Export CSV cu filtrele curente (max 10k rânduri, cele mai recente primele)."""
    rows = await audit_service.list_all_filtered(
        session,
        admin.tenant_id,
        event_type=event_type,
        event_prefix=event_prefix,
        user_id=user_id,
        since=_parse_dt(since),
        until=_parse_dt(until),
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "created_at", "event_type", "user_id", "target_type", "target_id",
        "ip_address", "user_agent", "metadata",
    ])
    for r in rows:
        writer.writerow([
            r.created_at.isoformat(),
            r.event_type,
            str(r.user_id) if r.user_id else "",
            r.target_type or "",
            str(r.target_id) if r.target_id else "",
            r.ip_address or "",
            r.user_agent or "",
            json.dumps(r.event_metadata, ensure_ascii=False) if r.event_metadata else "",
        ])
    buf.seek(0)

    filename = f"audit-log-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
