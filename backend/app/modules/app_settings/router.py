"""Router pentru /api/settings — AI keys și alte setări tenant."""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.app_settings import service as svc
from app.modules.auth.deps import get_current_tenant_id

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AiKeyUpdate(BaseModel):
    provider: str  # "anthropic" | "openai" | "xai" | "deepseek"
    key: str | None = None  # None sau "" = șterge


@router.get("/ai-keys")
async def api_get_ai_keys(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Returnează chei AI configurate (mascate pentru UI)."""
    return {"ok": True, "keys": await svc.get_ai_keys(session, tenant_id)}


@router.put("/ai-keys")
async def api_set_ai_key(
    body: AiKeyUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Setează/șterge cheia unui provider. Body: { provider, key }."""
    # Validare minimă pe prefix (prevenție copy-paste greșit)
    k = (body.key or "").strip()
    prefixes = {
        "anthropic": "sk-ant-",
        "openai":    "sk-",
        "xai":       "xai-",
        "deepseek":  "sk-",
    }
    if k:
        expected = prefixes.get(body.provider.lower())
        if expected and not k.startswith(expected):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"Cheia pentru {body.provider} trebuie să înceapă cu '{expected}'",
            )
    try:
        await svc.save_ai_key(session, tenant_id, body.provider, k or None)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}
