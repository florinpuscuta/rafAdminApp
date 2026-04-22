"""App settings service — get/set chei per tenant."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.app_settings.models import AppSetting


# ── AI key prefixes — validation ────────────────────────────────────────────
_AI_KEY_NAMES = {"anthropic", "openai", "xai", "deepseek"}


async def get_setting(
    session: AsyncSession, tenant_id: UUID, key: str,
) -> str | None:
    row = (await session.execute(
        select(AppSetting.value).where(
            AppSetting.tenant_id == tenant_id, AppSetting.key == key,
        )
    )).scalar_one_or_none()
    return row


async def set_setting(
    session: AsyncSession, tenant_id: UUID, key: str, value: str | None,
) -> None:
    """Upsert o setare."""
    if value is None or value == "":
        await session.execute(
            delete(AppSetting).where(
                AppSetting.tenant_id == tenant_id, AppSetting.key == key,
            )
        )
    else:
        stmt = pg_insert(AppSetting).values(
            tenant_id=tenant_id, key=key, value=value,
        ).on_conflict_do_update(
            index_elements=["tenant_id", "key"],
            set_={"value": value},
        )
        await session.execute(stmt)
    await session.commit()


async def get_ai_keys(session: AsyncSession, tenant_id: UUID) -> dict[str, str | None]:
    """Returnează dict {provider: key} pentru UI. Keys masked (doar prefix)."""
    rows = (await session.execute(
        select(AppSetting.key, AppSetting.value).where(
            AppSetting.tenant_id == tenant_id,
            AppSetting.key.in_([f"ai_key_{n}" for n in _AI_KEY_NAMES]),
        )
    )).all()
    out: dict[str, str | None] = {n: None for n in _AI_KEY_NAMES}
    for k, v in rows:
        name = k.replace("ai_key_", "")
        if v:
            # Mask: show only first 8 + "..." + last 4
            masked = f"{v[:10]}...{v[-4:]}" if len(v) > 14 else v
            out[name] = masked
    return out


async def save_ai_key(
    session: AsyncSession, tenant_id: UUID, provider: str, key: str | None,
) -> None:
    """Salvează/șterge cheia unui provider. key=None/'' → șterge."""
    provider = provider.lower().strip()
    if provider not in _AI_KEY_NAMES:
        raise ValueError(f"Provider necunoscut: {provider}")
    await set_setting(session, tenant_id, f"ai_key_{provider}", key)


async def get_raw_ai_key(
    session: AsyncSession, tenant_id: UUID, provider: str,
) -> str | None:
    """Returnează cheia efectivă (NU mascată) — folosită de ai_update_service."""
    return await get_setting(session, tenant_id, f"ai_key_{provider}")
