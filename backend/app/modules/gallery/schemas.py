from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema

FolderType = Literal["magazine", "catalog", "concurenta", "panouri", "competition", "other"]


class FolderOut(APISchema):
    id: UUID
    type: str
    name: str
    created_at: datetime
    photo_count: int = 0


class CreateFolderRequest(APISchema):
    type: FolderType = "magazine"
    name: str = Field(min_length=1, max_length=200)


class PhotoOut(APISchema):
    id: UUID
    folder_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    caption: str | None
    uploaded_by_user_id: UUID | None
    uploaded_at: datetime
    url: str  # presigned URL — 1h TTL
    approval_status: str = "approved"


class PendingPhotoOut(PhotoOut):
    folder_type: str
    folder_name: str


class PendingSummary(APISchema):
    pending_count: int
