from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ConversationOut(APISchema):
    id: UUID
    title: str
    user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class MessageOut(APISchema):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    created_at: datetime


class CreateConversationRequest(APISchema):
    title: str | None = Field(default=None, max_length=200)


class SendMessageRequest(APISchema):
    content: str = Field(min_length=1, max_length=8000)


class SendMessageResponse(APISchema):
    user_message: MessageOut
    assistant_message: MessageOut
    provider: str  # "anthropic" | "stub"
