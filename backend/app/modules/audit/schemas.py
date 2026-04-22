from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.schemas import APISchema


class AuditLogOut(APISchema):
    id: UUID
    tenant_id: UUID | None
    user_id: UUID | None
    event_type: str
    target_type: str | None
    target_id: UUID | None
    event_metadata: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditLogListResponse(APISchema):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
