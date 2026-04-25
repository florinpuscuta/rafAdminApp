"""
AI Assistant service. Provider-agnostic, cu tool use (SQL read-only).

Provideri suportați (toți cu tool use):
- Anthropic (format native)
- OpenAI / xAI / DeepSeek (format function calling)

Tool-ul `query_db` rulează SQL SELECT validat (vezi `ai/tools.py`).
"""
import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.ai.models import AIConversation, AIMessage
from app.modules.ai.tools import (
    ANTHROPIC_TOOLS,
    OPENAI_TOOLS,
    dispatch_tool,
    list_memories,
)
from app.modules.app_settings.service import get_raw_ai_key

log = logging.getLogger("adeplast.ai")


SCHEMA_HINT = """\
Schema aplicației (PostgreSQL). Toate tabelele "de business" au coloana
`tenant_id` (UUID) — TREBUIE inclus în WHERE pe orice query.

DATE DE VÂNZĂRI:
- `raw_sales` (tenant_id, year, month, store_id, agent_id, product_id,
  amount NUMERIC, qty NUMERIC, channel TEXT, client TEXT, ship_to TEXT,
  batch_id, ...). Sursa de adevăr a vânzărilor; un rând per linie de factură.
  `channel='KA'` sunt KA-urile (Dedeman, Altex, Leroy, Hornbach + Bricostore).
- `import_batches` (id, tenant_id, source TEXT, ...). `source` indică firma:
  'sales_xlsx' = Adeplast, 'sika_mtd_xlsx' / 'sika_xlsx' = Sika.
  JOIN cu raw_sales pe `import_batches.id = raw_sales.batch_id`.

CLIENȚI ȘI MAGAZINE:
- `store_agent_mappings` (tenant_id, source, client_original, ship_to_original,
  cheie_finala, agent_unificat, store_id, agent_id). SURSA DE ADEVĂR pentru
  ierarhia client→magazin. `client_original` listează clienții; valorile reale:
    'DEDEMAN SRL', 'ALTEX ROMANIA SRL', 'LEROY MERLIN ROMANIA SRL',
    'HORNBACH CENTRALA SRL', 'BRICOSTORE ROMANIA SA/SRL'.
  Pentru fiecare client, lista magazinelor canonice = SELECT DISTINCT store_id.
- `stores` (id, tenant_id, name, chain, city, active). Magazinul canonic.
- `store_aliases` (tenant_id, raw_client, store_id). Maparea text-brut→Store
  (din UI Mapări). Folosită doar dacă raw_sales.store_id e NULL.

PRODUSE / AGENȚI:
- `products` (id, tenant_id, code, name, category, brand_id, ...).
- `product_categories`, `brands` — taxonomie.
- `agents` (id, tenant_id, full_name, code, ...).

ALTELE:
- `targhet_growth_pct` — target-uri de creștere per agent/lună.
- `agent_visits` — vizite de teren ale agenților.
- `tasks`, `task_assignments` — task management.
- `panouri_standuri` — panouri publicitare.
- `facing_*` — facing pe raft.

CONVENȚII:
- Sume în RON, fără TVA — `raw_sales.amount`.
- "YTD" = SUM(amount) WHERE year = anul curent (sau cel cerut).
- Pentru ranking-uri, folosește func.count(DISTINCT product_id) pentru SKU-uri.
"""


SYSTEM_PROMPT = (
    "Ești un asistent AI specializat pe date de vânzări și operațiuni "
    "comerciale pentru Adeplast / Sika (platforma SaaS Raf-AdminApp). "
    "Răspunzi în română, clar și concis. Toate cifrele să fie corecte — "
    "atunci când nu ești sigur, INTEROGHEAZĂ baza de date prin tool-uri "
    "în loc să ghicești.\n\n"
    "TOOL-URI DISPONIBILE:\n"
    "- `query_db(sql)` — citire (SELECT/WITH).\n"
    "- `propose_write(sql)` — propune o modificare (INSERT/UPDATE/DELETE), "
    "face dry-run, întoarce un TOKEN. NU modifică încă nimic.\n"
    "- `execute_write(token)` — commit-uie modificarea propusă. SE CHEAMĂ "
    "DOAR DUPĂ ce utilizatorul confirmă explicit în chat (ex: 'da', 'execută').\n"
    "- `remember(key, value)` — salvează o preferință / context persistent "
    "tenant-wide (ex: anul implicit, scope-ul preferat, terminologie). "
    "Se încarcă automat în prompt la fiecare conversație nouă.\n"
    "- `forget(key)` — șterge o memorie persistentă.\n\n"
    "REGULI:\n"
    "1. Pentru cifre / liste / clasamente / comparații: folosește `query_db`. "
    "Nu inventa numere.\n"
    "2. Include MEREU `tenant_id = '<uuid-ul curent>'` (vezi mai jos) în "
    "WHERE pentru orice tabelă cu tenant_id (read SAU write).\n"
    "3. Pattern de scriere OBLIGATORIU: (a) `propose_write` întâi, "
    "(b) raportează utilizatorului ce ai propus + numărul de rânduri "
    "afectate + token-ul, (c) AȘTEAPTĂ confirmarea, (d) abia apoi "
    "`execute_write`. Niciodată să nu execuți fără confirmare.\n"
    "4. Dacă un query întoarce 0 rânduri, încearcă variantă (alt an, "
    "filtru mai lax). Nu te opri la primul rezultat gol.\n"
    "5. Verifică schema cu `information_schema.columns` dacă ai nevoie.\n"
    "6. Max 200 rânduri pe read — folosește GROUP BY pentru date mari.\n\n"
    f"{SCHEMA_HINT}"
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

MAX_TOOL_ITERATIONS = 8
# Răspunsuri suficient de lungi pentru analize cu rezultate SQL în context.
MAX_TOKENS = 8192


async def _effective_key(
    session: AsyncSession, tenant_id: UUID, provider: str,
) -> str | None:
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


async def _system_prompt_for(session: AsyncSession, tenant_id: UUID) -> str:
    """System prompt = bază + UUID tenant + memoria persistentă încărcată."""
    base = (
        SYSTEM_PROMPT
        + f"\n\nUUID-UL TENANT-ULUI CURENT (folosește-l în WHERE): {tenant_id}\n"
    )
    memories = await list_memories(session, tenant_id)
    if not memories:
        return base
    lines = "\n".join(f"- `{m['key']}`: {m['value']}" for m in memories)
    return (
        base
        + "\nMEMORIA TA PERSISTENTĂ (preferințe / context salvat anterior):\n"
        + lines
        + "\nFolosește aceste valori implicit. Dacă utilizatorul cere "
        + "schimbarea unei preferințe, folosește `remember` ca s-o "
        + "actualizezi.\n"
    )


# --------------------------------------------------------------------------
# Anthropic native tool use loop
# --------------------------------------------------------------------------
async def _call_anthropic(
    session: AsyncSession,
    tenant_id: UUID,
    history: list[AIMessage],
    user_content: str,
    *,
    api_key: str,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    messages: list[dict] = [
        {"role": m.role, "content": m.content}
        for m in history
        if m.role in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": user_content})

    system = await _system_prompt_for(session, tenant_id)

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=ANTHROPIC_TOOLS,
            messages=messages,
        )

        if resp.stop_reason != "tool_use":
            parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
            return "".join(parts) or "(răspuns gol)"

        # Append răspunsul modelului (cu tool_use blocks) în istoric.
        messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})

        tool_results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            tool_name = block.name
            tool_input = block.input or {}
            log.info(
                "AI tool %s: %s", tool_name,
                json.dumps(tool_input, ensure_ascii=False, default=str)[:200],
            )
            result = await dispatch_tool(session, tenant_id, tool_name, tool_input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:8000],
            })

        messages.append({"role": "user", "content": tool_results})

    return (
        "(am atins limita de iterații pe tool use; reformulează întrebarea "
        "sau cere un singur query țintă)"
    )


# --------------------------------------------------------------------------
# OpenAI-compat (OpenAI / xAI / DeepSeek) function calling loop
# --------------------------------------------------------------------------
async def _call_openai_compat(
    session: AsyncSession,
    tenant_id: UUID,
    history: list[AIMessage],
    user_content: str,
    *,
    api_key: str,
    model: str,
    base_url: str | None,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    sys_prompt = await _system_prompt_for(session, tenant_id)
    messages: list[dict] = [{"role": "system", "content": sys_prompt}]
    for m in history:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_content})

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=OPENAI_TOOLS,
            max_tokens=MAX_TOKENS,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content or "(răspuns gol)"

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            log.info(
                "AI tool %s (%s): %s", tc.function.name, model,
                json.dumps(args, ensure_ascii=False, default=str)[:200],
            )
            result = await dispatch_tool(session, tenant_id, tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str)[:8000],
            })

    return (
        "(am atins limita de iterații pe tool use; reformulează întrebarea "
        "sau cere un singur query țintă)"
    )


async def _call_llm(
    session: AsyncSession,
    tenant_id: UUID,
    provider: str,
    history: list[AIMessage],
    user_content: str,
    *,
    api_key: str,
) -> str:
    if provider == "anthropic":
        return await _call_anthropic(
            session, tenant_id, history, user_content, api_key=api_key
        )
    cfg = PROVIDERS[provider]
    return await _call_openai_compat(
        session,
        tenant_id,
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
    Persistă mesajul user-ului, apelează providerul (cu tool use), persistă
    răspunsul. Returnează (user_message, assistant_message, provider_name).
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
            assert api_key is not None
            assistant_text = await _call_llm(
                session, conv.tenant_id, provider, history, user_content,
                api_key=api_key,
            )
    except Exception as exc:  # noqa: BLE001
        log.exception("AI provider error")
        assistant_text = f"⚠️ Eroare provider `{provider}`: {exc}"
        provider = f"error:{provider}"

    assistant_msg = AIMessage(
        conversation_id=conv.id, role="assistant", content=assistant_text
    )
    session.add(assistant_msg)
    conv.updated_at = user_msg.created_at or conv.updated_at

    if conv.title == "Conversație nouă" and not history:
        conv.title = user_content[:80] + ("…" if len(user_content) > 80 else "")

    await session.commit()
    await session.refresh(user_msg)
    await session.refresh(assistant_msg)
    return user_msg, assistant_msg, provider
