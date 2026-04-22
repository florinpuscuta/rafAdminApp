from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class TenantOut(APISchema):
    id: UUID
    name: str
    slug: str
    active: bool
    created_at: datetime


class UpdateTenantRequest(APISchema):
    name: str | None = Field(default=None, min_length=2, max_length=200)
