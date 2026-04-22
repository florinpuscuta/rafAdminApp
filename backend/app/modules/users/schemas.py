from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field

from app.core.schemas import APISchema

UserRole = Literal["admin", "manager", "member", "viewer"]


class UserOut(APISchema):
    id: UUID
    tenant_id: UUID
    email: str
    role: str
    active: bool
    created_at: datetime
    last_login_at: datetime | None = None
    email_verified: bool
    email_verified_at: datetime | None = None
    totp_enabled: bool = False


class CreateUserRequest(APISchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "member"


class UpdateUserRequest(APISchema):
    role: UserRole | None = None
    active: bool | None = None
