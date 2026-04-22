from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ApiKeyOut(APISchema):
    id: UUID
    name: str
    prefix: str
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class CreateApiKeyRequest(APISchema):
    name: str = Field(min_length=1, max_length=100)


class CreateApiKeyResponse(APISchema):
    api_key: ApiKeyOut
    # Arătat DOAR la creare — stocat hashuit, nu mai poate fi recuperat ulterior
    secret: str
