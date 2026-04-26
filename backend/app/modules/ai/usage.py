"""
Helper pentru loguirea utilizării AI per tenant. Fail-soft — dacă insert-ul
eșuează, AI-ul răspunde corect, doar pierdem tracking-ul pentru acel call.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.ai.models import AIUsageLog
from app.modules.ai.pricing import calc_cost_usd

logger = logging.getLogger("adeplast.ai.usage")


async def log_ai_usage(
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int | None = None,
    session: AsyncSession | None = None,
) -> None:
    """
    Salvează un rând în `ai_usage_log`. Folosește o sesiune nouă dacă nu primește
    una — astfel callerul nu trebuie să gestioneze tranzacții.
    """
    cost = calc_cost_usd(model, input_tokens, output_tokens)

    own_session = session is None
    if session is None:
        session = SessionLocal()  # type: ignore[assignment]

    try:
        row = AIUsageLog(
            tenant_id=tenant_id,
            user_id=user_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        session.add(row)  # type: ignore[union-attr]
        if own_session:
            await session.commit()  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("log_ai_usage failed: %s", exc)
        if own_session:
            try:
                await session.rollback()  # type: ignore[union-attr]
            except Exception:
                pass
    finally:
        if own_session:
            try:
                await session.close()  # type: ignore[union-attr]
            except Exception:
                pass
