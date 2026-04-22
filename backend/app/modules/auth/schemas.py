from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.core.schemas import APISchema
from app.modules.tenants.schemas import TenantOut
from app.modules.users.schemas import UserOut


class SignupRequest(APISchema):
    tenant_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(APISchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, min_length=6, max_length=6)


class AuthResponse(APISchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    tenant: TenantOut


class RefreshRequest(APISchema):
    refresh_token: str = Field(min_length=10, max_length=128)


class TokenPair(APISchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(APISchema):
    refresh_token: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(APISchema):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class RequestPasswordResetRequest(APISchema):
    email: EmailStr


class ConfirmPasswordResetRequest(APISchema):
    token: str = Field(min_length=10, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ConfirmEmailVerifyRequest(APISchema):
    token: str = Field(min_length=10, max_length=128)


class TOTPSetupResponse(APISchema):
    secret: str           # raw base32 secret (afișat o singură dată)
    provisioning_uri: str # otpauth://... — pentru QR


class TOTPCodeRequest(APISchema):
    code: str = Field(min_length=6, max_length=6)


class CreateInvitationRequest(APISchema):
    email: EmailStr
    role: str = Field(default="member")


class InvitationOut(APISchema):
    id: UUID
    email: str
    role: str
    invited_by_user_id: UUID | None
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class AcceptInvitationRequest(APISchema):
    token: str = Field(min_length=10, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class BulkInviteResponse(APISchema):
    invited: int
    skipped: int
    errors: list[str]
