from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.ai import service as ai_service
from app.modules.ai.schemas import (
    ConversationOut,
    CreateConversationRequest,
    MessageOut,
    SendMessageRequest,
    SendMessageResponse,
)
from app.modules.auth.deps import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convs = await ai_service.list_conversations(session, current_user.tenant_id)
    return [ConversationOut.model_validate(c) for c in convs]


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = await ai_service.create_conversation(
        session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        title=payload.title,
    )
    return ConversationOut.model_validate(conv)


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = await ai_service.get_conversation(session, current_user.tenant_id, conv_id)
    if conv is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Conversație inexistentă"},
        )
    await ai_service.delete_conversation(session, conv)
    return None


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conv_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = await ai_service.get_conversation(session, current_user.tenant_id, conv_id)
    if conv is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Conversație inexistentă"},
        )
    msgs = await ai_service.list_messages(session, conv_id)
    return [MessageOut.model_validate(m) for m in msgs]


@router.post(
    "/conversations/{conv_id}/messages", response_model=SendMessageResponse
)
async def send_message(
    conv_id: UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = await ai_service.get_conversation(session, current_user.tenant_id, conv_id)
    if conv is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Conversație inexistentă"},
        )
    user_msg, asst_msg, provider = await ai_service.send_message(
        session, conv, payload.content
    )
    return SendMessageResponse(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(asst_msg),
        provider=provider,
    )
