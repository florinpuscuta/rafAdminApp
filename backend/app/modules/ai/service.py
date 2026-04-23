"""
AI Assistant service. Provider-agnostic:
- Dacă `ANTHROPIC_API_KEY` e setat → Anthropic Claude API
- Altfel → stub diagnostic ("configurează ANTHROPIC_API_KEY...")

Contextul conversației (mesaje anterioare) e transmis la fiecare apel.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.ai.models import AIConversation, AIMessage
from app.modules.app_settings.service import get_raw_ai_key

log = logging.getLogger("adeplast.ai")

SYSTEM_PROMPT = (
    "Ești un asistent AI specializat pe date de vânzări KA pentru Adeplast. "
    "Utilizatorul administrează date de vânzări prin platforma SaaS. "
    "Răspunde clar, concis, în română. Dacă nu ai suficient context, spune-o."
)


PROVIDERS = {
    "anthropic": {"key_attr": "anthropic_api_key", "model_attr": "anthropic_model"},
    "openai": {"key_attr": "openai_api_key", "model_attr": "openai_model", "base_url": None},
    "xai": {"key_attr": "xai_api_key", "model_attr": "xai_model", "base_url": "https://api.x.ai/v1"},
    "deepseek": {
        "key_attr": "deepseek_api_key",
        "model_attr": "deepseek_model",
        "base_url": "https://api.deepseek.com/v1",
    },
}


async def _effective_key(
    session: AsyncSession, tenant_id: UUID, provider: str,
) -> str | None:
    """Cheia efectivă pentru `provider`: preferăm DB (per tenant), fallback pe env."""
    db_key = await get_raw_ai_key(session, tenant_id, provider)
    if db_key:
        return db_key
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return None
    return getattr(settings, cfg["key_attr"], None)


async def _detect_provider(
    session: AsyncSession, tenant_id: UUID,
) -> str | None:
    """Forțat prin settings.ai_provider (dacă are key setat), altfel primul provider
    cu key disponibil — DB tenant-scoped câștigă peste env."""
    if settings.ai_provider and settings.ai_provider in PROVIDERS:
        if await _effective_key(session, tenant_id, settings.ai_provider):
            return settings.ai_provider
    for name in ("anthropic", "openai", "xai", "deepseek"):
        if await _effective_key(session, tenant_id, name):
            return name
    return None


async def list_conversations(
    session: AsyncSession, tenant_id: UUID
) -> list[AIConversation]:
    stmt = (
        select(AIConversation)
        .where(AIConversation.tenant_id == tenant_id)
        .order_by(AIConversation.updated_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_conversation(
    session: AsyncSession, tenant_id: UUID, conv_id: UUID
) -> AIConversation | None:
    result = await session.execute(
        select(AIConversation).where(
            AIConversation.id == conv_id, AIConversation.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def create_conversation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    title: str | None = None,
) -> AIConversation:
    conv = AIConversation(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title or "Conversație nouă",
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def delete_conversation(session: AsyncSession, conv: AIConversation) -> None:
    await session.delete(conv)
    await session.commit()


async def list_messages(
    session: AsyncSession, conv_id: UUID
) -> list[AIMessage]:
    stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conv_id)
        .order_by(AIMessage.created_at)
    )
    return list((await session.execute(stmt)).scalars().all())


def _chat_history(history: list[AIMessage], user_content: str) -> list[dict]:
    msgs = [
        {"role": m.role, "content": m.content}
        for m in history
        if m.role in ("user", "assistant")
    ]
    msgs.append({"role": "user", "content": user_content})
    return msgs


def _call_anthropic(history: list[AIMessage], user_content: str, *, api_key: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=_chat_history(history, user_content),
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "".join(parts) or "(răspuns gol)"


def _call_openai_compat(
    history: list[AIMessage],
    user_content: str,
    *,
    api_key: str,
    model: str,
    base_url: str | None,
) -> str:
    """Apel prin OpenAI SDK — folosit pentru OpenAI propriu-zis, xAI, DeepSeek."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _chat_history(history, user_content)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=1024,
    )
    return resp.choices[0].message.content or "(răspuns gol)"


def _call_llm(
    provider: str, history: list[AIMessage], user_content: str, *, api_key: str,
) -> str:
    if provider == "anthropic":
        return _call_anthropic(history, user_content, api_key=api_key)
    cfg = PROVIDERS[provider]
    return _call_openai_compat(
        history,
        user_content,
        api_key=api_key,
        model=getattr(settings, cfg["model_attr"]),
        base_url=cfg.get("base_url"),
    )


async def send_message(
    session: AsyncSession,
    conv: AIConversation,
    user_content: str,
) -> tuple[AIMessage, AIMessage, str]:
    """
    Persistă mesajul user-ului, apelează providerul, persistă răspunsul.
    Returnează (user_message, assistant_message, provider_name).
    """
    history = await list_messages(session, conv.id)

    user_msg = AIMessage(conversation_id=conv.id, role="user", content=user_content)
    session.add(user_msg)
    await session.flush()

    provider = await _detect_provider(session, conv.tenant_id)
    try:
        if provider is None:
            provider = "stub"
            assistant_text = (
                "ℹ️ AI Assistant e în mod stub (niciun provider configurat). "
                "Setează o cheie în Settings → Chei AI sau una dintre variabilele "
                "`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY` "
                "în `.env` și repornește backend-ul. Opțional `AI_PROVIDER=<nume>` ca să "
                "forțezi un provider anume."
            )
        else:
            api_key = await _effective_key(session, conv.tenant_id, provider)
            assert api_key is not None  # _detect_provider a confirmat prezența
            assistant_text = _call_llm(provider, history, user_content, api_key=api_key)
    except Exception as exc:  # noqa: BLE001 — orice eroare LLM → mesaj lizibil
        log.exception("AI provider error")
        assistant_text = f"⚠️ Eroare provider `{provider}`: {exc}"
        provider = f"error:{provider}"

    assistant_msg = AIMessage(
        conversation_id=conv.id, role="assistant", content=assistant_text
    )
    session.add(assistant_msg)
    # actualizează updated_at pe conversație
    conv.updated_at = user_msg.created_at or conv.updated_at

    # Auto-title: dacă titlul e default și e primul mesaj real, folosim început-ul
    if conv.title == "Conversație nouă" and not history:
        conv.title = user_content[:80] + ("…" if len(user_content) > 80 else "")

    await session.commit()
    await session.refresh(user_msg)
    await session.refresh(assistant_msg)
    return user_msg, assistant_msg, provider
