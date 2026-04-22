"""Generare narațiune AI pe baza numerelor deja calculate.

Principiu: LLM primește JSON compact cu numerele gata agregate și produce
narațiune structurată (3-5 paragrafe) în română. Nu inventează cifre.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from uuid import UUID

import asyncpg

log = logging.getLogger("adeplast.monthly_report")

MONTHS_RO = [
    "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]


_SYSTEM_PROMPT_BASE = (
    "Ești un analist senior de vânzări KA pentru RAF Consulting, care scrie "
    "rapoarte lunare despre canalul Adeplast + Sika. Scrii în română, ton "
    "profesional, analitic, cu cifre exacte din datele primite. "
    "NU INVENTA cifre — folosește doar numerele din JSON-ul primit. "
    "Nu menționa agenți — doar branduri, clienți (lanțuri KA: Dedeman, Hornbach, Leroy Merlin, Altex, etc.), "
    "zone geografice, grupe de produse."
)


async def _get_provider_key_from_db(
    tenant_id: UUID, provider: str,
) -> str | None:
    dsn = os.environ.get("DATABASE_URL", "")
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    if not dsn:
        return None
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchval(
            "SELECT value FROM app_settings WHERE tenant_id=$1::uuid AND key=$2",
            str(tenant_id), f"ai_key_{provider}",
        )
        return (row or "").strip() or None
    finally:
        await conn.close()


async def _select_provider(tenant_id: UUID) -> tuple[str, str] | None:
    for p in ("anthropic", "xai", "openai", "deepseek"):
        k = await _get_provider_key_from_db(tenant_id, p)
        if k:
            return (p, k)
        env_key = {
            "xai": "XAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }[p]
        env_val = (os.environ.get(env_key) or "").strip()
        if env_val:
            return (p, env_val)
    return None


def _call_openai_compat(
    *, api_key: str, model: str, base_url: str | None,
    system: str, user: str, max_tokens: int = 700,
) -> str:
    from openai import OpenAI

    client = (
        OpenAI(api_key=api_key, base_url=base_url) if base_url
        else OpenAI(api_key=api_key)
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(
    *, api_key: str, system: str, user: str, max_tokens: int = 700,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "".join(parts)


async def _narrate(
    tenant_id: UUID,
    *,
    system_extra: str,
    dossier_json: dict,
    user_instruction: str,
    max_tokens: int = 700,
) -> str:
    picked = await _select_provider(tenant_id)
    if not picked:
        return "(Narațiunea AI nu e disponibilă — nu s-a găsit nicio cheie API configurată în app_settings.)"

    provider, api_key = picked
    system = _SYSTEM_PROMPT_BASE + "\n\n" + system_extra
    user = (
        f"{user_instruction}\n\n"
        f"Date (nu inventa nimic, folosește fix cifrele de mai jos):\n"
        f"```json\n{json.dumps(dossier_json, ensure_ascii=False, indent=2)}\n```"
    )

    try:
        if provider == "anthropic":
            result = await asyncio.to_thread(
                _call_anthropic,
                api_key=api_key, system=system, user=user, max_tokens=max_tokens,
            )
            return (result or "").strip()
        base_urls = {
            "xai": "https://api.x.ai/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "openai": None,
        }
        models = {
            "xai": "grok-4-fast",
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o-mini",
        }
        result = await asyncio.to_thread(
            _call_openai_compat,
            api_key=api_key, model=models[provider], base_url=base_urls[provider],
            system=system, user=user, max_tokens=max_tokens,
        )
        return (result or "").strip()
    except Exception as e:
        log.exception("narrator call failed")
        return f"(Narațiunea AI a eșuat: {e})"


# ─────────────────────────────────────────────────────────────────────────
# Prompts per secțiune
# ─────────────────────────────────────────────────────────────────────────

async def narrate_executive_summary(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii sumarul executiv de ansamblu al raportului (INTRO). "
            "Lungime: 3 paragrafe, fiecare 3-4 propoziții."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            f"Scrie sumarul executiv pentru luna {MONTHS_RO[dossier_json.get('month', 0)]} "
            f"{dossier_json.get('year')}. Include: (1) total KA luna + YoY, "
            "(2) comparație Adeplast vs Sika, (3) context consolidat."
        ),
        max_tokens=700,
    )


async def narrate_brand_section(
    tenant_id: UUID, brand: str, dossier_json: dict,
) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            f"Scrii secțiunea '{brand} Key Accounts' din raportul lunar. "
            "3 paragrafe: (1) Analiza valorică + volumetrică YoY (includ procentele), "
            "(2) Divergența preț vs volum (dacă există), interpretare, "
            "(3) Riscuri și context."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            f"Scrie analiza pentru {brand} Key Accounts. 3 paragrafe. "
            "Discuta valoric + volumetric YoY, YTD, trendurile."
        ),
        max_tokens=800,
    )


async def narrate_clients_section(
    tenant_id: UUID, brand: str, dossier_json: dict,
) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii analiza top clienți KA (Dedeman, Hornbach, Leroy Merlin, etc.). "
            "Lungime: 1-2 paragrafe."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            f"Analizează vânzările top clienți KA la {brand}. Menționează ponderea principalului client, "
            "câștigătorii și perdanții vs anul anterior."
        ),
        max_tokens=500,
    )


async def narrate_categories_section(
    tenant_id: UUID, brand: str, dossier_json: dict,
) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii analiza grupelor de produse KA (EPS, MU, Umede, Dibluri, Paleți, etc.). "
            "Lungime: 1-2 paragrafe."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            f"Analizează grupele de produse {brand}. "
            "Evidențiază categoria dominantă și cele în creștere/scădere."
        ),
        max_tokens=500,
    )


async def narrate_marca_privata(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii secțiunea 'Marcă Privată' pentru Adeplast. "
            "Lungime: 1 paragraf bogat."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            "Analizează performanța Mărcii Private vs Adeplast brand — procent din total, "
            "evoluție YoY, categoriile cu creștere."
        ),
        max_tokens=400,
    )


async def narrate_consolidated(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii secțiunea 'Analiza Consolidată — Adeplast + Sika'. "
            "Lungime: 2 paragrafe."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            "Scrie analiza portofoliului consolidat: ponderile Adeplast/Sika, "
            "top clienți consolidați YTD, dependența de clientul principal."
        ),
        max_tokens=600,
    )


async def narrate_conclusions(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii secțiunea 'Concluzii și Recomandări Strategice'. "
            "Format: numerotat [1]-[5] puncte principale + listă de 4-6 recomandări prioritare. "
            "Fiecare punct = 2-3 propoziții concrete."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            "Scrie concluziile raportului: 5 puncte numerotate (riscuri, oportunități, "
            "dependențe, tendințe), urmate de un titlu 'Recomandări Prioritare' cu 4-6 "
            "recomandări concrete per brand sau per client."
        ),
        max_tokens=1000,
    )


async def narrate_prices(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii secțiunea 'Analiza Prețurilor KA vs Competitori'. "
            "Lungime: 2 paragrafe."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            "Analizează poziționarea prețurilor Adeplast vs competitori în top retaileri KA. "
            "Evidențiază: (1) avantajul mediu % Adeplast vs concurenții (cheaper/expensive), "
            "(2) produsele cu cel mai mare decalaj. "
            "Nu inventa nimic, folosește doar cifrele din JSON."
        ),
        max_tokens=500,
    )


async def narrate_marketing(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii secțiunea 'Activități Marketing' (catalog lunar, panouri, prezență raft). "
            "Lungime: 2 paragrafe. Menționează volumele de activitate."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            "Analizează activitatea de marketing a lunii: câte panouri active sunt montate, "
            "câte poze de raft/magazin s-au făcut, dacă există catalog dedicat lunii. "
            "Comentează rolul suportului de marketing în performanța comercială."
        ),
        max_tokens=500,
    )


async def narrate_zones(tenant_id: UUID, dossier_json: dict) -> str:
    return await _narrate(
        tenant_id,
        system_extra=(
            "Scrii secțiunea 'Vânzări pe zone geografice'. "
            "Lungime: 2 paragrafe."
        ),
        dossier_json=dossier_json,
        user_instruction=(
            "Analizează distribuția vânzărilor pe zone (orașe/județe). "
            "Menționează variația totală YoY, top 2 zone în creștere absolută, "
            "top 2 zone în scădere. Nu menționa agenți — doar zone geografice."
        ),
        max_tokens=500,
    )
