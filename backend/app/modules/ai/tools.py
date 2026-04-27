"""
Tool use pentru asistentul AI: SQL read-only + scriere cu confirmare.

Reguli de siguranță:
- READ: SELECT/WITH only, statement_timeout, max 200 rânduri, tabele de
  credențiale blocate, tenant_id obligatoriu în WHERE.
- WRITE: pattern propose→execute. `propose_write` validează SQL-ul de
  modificare, calculează un dry-run (câte rânduri afectează), salvează
  un token. AI-ul îl raportează utilizatorului. Doar dacă userul confirmă
  în chat ("da", "execută", etc.) AI-ul cheamă `execute_write(token)`,
  care commit-uie efectiv. Token-urile expiră în 15 minute.
"""
from __future__ import annotations

import re
import secrets
import time
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import AIMemory


# Doar credențiale & token-uri rămân blocate — n-au valoare informativă
# pentru AI și diminuează riscul în caz de halucinație.
BLOCKED_TABLES: frozenset[str] = frozenset({
    "api_keys",
    "app_settings",            # conține chei AI criptate
    "password_reset_tokens",
    "email_verification_tokens",
    "refresh_tokens",
})

MAX_ROWS = 200
STATEMENT_TIMEOUT_MS = 8000
WRITE_TOKEN_TTL_SEC = 900     # 15 min

_SELECT_PREFIX = re.compile(r"^\s*(?:--[^\n]*\n|\s)*\s*(select|with)\b", re.IGNORECASE)
_WRITE_PREFIX = re.compile(
    r"^\s*(?:--[^\n]*\n|\s)*\s*(insert|update|delete)\b", re.IGNORECASE
)
_FORBIDDEN_READ_KEYWORDS = re.compile(
    r"\b(insert|update|delete|truncate|drop|alter|create|grant|revoke|"
    r"copy|comment|vacuum|reindex|cluster|lock|notify|listen|do|call)\b",
    re.IGNORECASE,
)
_FORBIDDEN_WRITE_KEYWORDS = re.compile(
    r"\b(truncate|drop|alter|create|grant|revoke|copy|vacuum|reindex|"
    r"cluster|notify|listen|do|call)\b",
    re.IGNORECASE,
)


def _json_safe(v):
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    return str(v)


def _check_blocked_tables(sql_lower: str) -> str | None:
    for tbl in BLOCKED_TABLES:
        if re.search(rf"\b{re.escape(tbl)}\b", sql_lower):
            return f"Acces refuzat la tabela `{tbl}` (sensibilă)."
    return None


# Identificatori (tabele + coloane) care expun datele despre agenți. Pentru
# rolul VIEWER blocăm orice query care le menționează — răspunsul AI nu
# poate dezvălui nume / performanță individuală.
_VIEWER_BLOCKED_IDENTS: tuple[str, ...] = (
    "agents", "agent_aliases", "agent_visits", "agent_store_assignments",
    "agent_store_bonus", "agent_compensation", "agent_month_inputs",
    "agent_id", "agent_unificat", "agent_original", "full_name",
)


def _check_viewer_block(sql_lower: str) -> str | None:
    """Pentru viewer: respinge orice SQL care atinge tabele / coloane despre agenți."""
    from app.modules.ai.context import current_viewer_mode
    if not current_viewer_mode.get():
        return None
    for ident in _VIEWER_BLOCKED_IDENTS:
        if re.search(rf"\b{re.escape(ident)}\b", sql_lower):
            return (
                f"Rolul tău (viewer) nu permite query-uri pe date despre "
                f"agenți. Identificator blocat: `{ident}`. Întreabă "
                f"despre totaluri agregate fără breakdown per agent."
            )
    return None


def _check_tenant(sql: str, tenant_ids: list[UUID]) -> str | None:
    """Validăm că SQL-ul referă cel puțin unul din UUID-urile autorizate.
    Pentru SIKADP user-ul are multiple org_ids și folosește
    `tenant_id IN ('uuid1','uuid2')` ca să acopere toate; altfel poate
    folosi `tenant_id = '<unul-dintre-uuid-uri>'`.
    """
    if not tenant_ids:
        return "Niciun tenant autorizat."
    if not any(str(t) in sql for t in tenant_ids):
        ids_str = ", ".join(f"'{t}'" for t in tenant_ids)
        return (
            f"Trebuie să incluzi cel puțin unul dintre UUID-urile autorizate "
            f"în WHERE (`tenant_id IN ({ids_str})` sau `tenant_id = ...`)."
        )
    return None


def _check_single_statement(sql: str) -> str | None:
    if ";" in sql.rstrip().rstrip(";"):
        return "Un singur statement pe apel (fără `;` în mijloc)."
    return None


def validate_sql(sql: str, tenant_ids: list[UUID]) -> str | None:
    """Validează SQL READ. Întoarce mesaj de eroare dacă e respins; None dacă e OK."""
    if not sql or not sql.strip():
        return "SQL gol."
    if (e := _check_single_statement(sql)) is not None:
        return e
    if not _SELECT_PREFIX.match(sql):
        return "Doar SELECT / WITH ... SELECT sunt permise."
    if _FORBIDDEN_READ_KEYWORDS.search(sql):
        return "Cuvinte cheie de modificare detectate (insert/update/delete/...)."
    if (e := _check_blocked_tables(sql.lower())) is not None:
        return e
    if (e := _check_viewer_block(sql.lower())) is not None:
        return e
    if (e := _check_tenant(sql, tenant_ids)) is not None:
        return e
    return None


async def run_sql_readonly(
    session: AsyncSession, tenant_ids: list[UUID], sql: str
) -> dict:
    """
    Rulează SQL-ul în tranzacție read-only cu timeout.
    Întoarce dict cu `columns`, `rows`, `row_count`, `truncated`, sau `error`.
    """
    err = validate_sql(sql, tenant_ids)
    if err:
        return {"error": err}

    # Sub-tranzacție ca să nu murdărim sesiunea principală.
    async with session.begin_nested() as sp:
        try:
            await session.execute(
                text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
            )
            await session.execute(text("SET LOCAL transaction_read_only = on"))
            result = await session.execute(text(sql))
            cols = list(result.keys())
            raw_rows = result.fetchmany(MAX_ROWS + 1)
            truncated = len(raw_rows) > MAX_ROWS
            rows = [
                {c: _json_safe(v) for c, v in zip(cols, r)}
                for r in raw_rows[:MAX_ROWS]
            ]
            await sp.rollback()  # nu commit — strict read-only.
            return {
                "columns": cols,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
            }
        except Exception as exc:  # noqa: BLE001 — orice eroare DB → mesaj lizibil
            await sp.rollback()
            return {"error": f"DB error: {exc}"}


# --------------------------------------------------------------------------
# Write pattern: propose → execute (cu confirmare manuală în chat)
# --------------------------------------------------------------------------
# Token store global per proces. Pentru utilizator solo (single-instance)
# e suficient. Dacă scalezi la mai mulți workeri, mută în Redis.
_PENDING_WRITES: dict[str, dict] = {}


def _gc_pending_writes() -> None:
    now = time.time()
    expired = [t for t, v in _PENDING_WRITES.items() if now - v["created_at"] > WRITE_TOKEN_TTL_SEC]
    for t in expired:
        _PENDING_WRITES.pop(t, None)


async def propose_write(
    session: AsyncSession, tenant_id: UUID, sql: str
) -> dict:
    """
    Validează SQL-ul de modificare, rulează un dry-run (BEGIN; sql; ROLLBACK;)
    ca să afle câte rânduri afectează, salvează un token. NU commit-uie.
    """
    _gc_pending_writes()
    err = validate_write_sql(sql, tenant_id)
    if err:
        return {"error": err}

    async with session.begin_nested() as sp:
        try:
            await session.execute(
                text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
            )
            result = await session.execute(text(sql))
            affected = result.rowcount
            await sp.rollback()  # dry-run: nu commit-uim niciodată aici.
        except Exception as exc:  # noqa: BLE001
            await sp.rollback()
            return {"error": f"DB error la dry-run: {exc}"}

    token = secrets.token_urlsafe(16)
    _PENDING_WRITES[token] = {
        "tenant_id": str(tenant_id),
        "sql": sql,
        "affected": affected,
        "created_at": time.time(),
    }
    return {
        "token": token,
        "affected_rows": affected,
        "ttl_seconds": WRITE_TOKEN_TTL_SEC,
        "message": (
            f"Dry-run: {affected} rânduri ar fi modificate. "
            "Cere CONFIRMAREA utilizatorului în chat înainte să apelezi "
            f"`execute_write` cu token-ul `{token}`."
        ),
    }


async def execute_write(
    session: AsyncSession, tenant_id: UUID, token: str
) -> dict:
    """Rulează SQL-ul stocat sub `token` și commit-uie."""
    _gc_pending_writes()
    pending = _PENDING_WRITES.get(token)
    if pending is None:
        return {"error": "Token invalid sau expirat. Re-cheamă `propose_write`."}
    if pending["tenant_id"] != str(tenant_id):
        return {"error": "Token aparține altui tenant — refuzat."}

    sql = pending["sql"]
    try:
        await session.execute(
            text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
        )
        result = await session.execute(text(sql))
        affected = result.rowcount
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        return {"error": f"DB error la execute: {exc}"}

    _PENDING_WRITES.pop(token, None)
    return {"committed": True, "affected_rows": affected}


# --------------------------------------------------------------------------
# Tool definitions (Anthropic native + OpenAI function calling)
# --------------------------------------------------------------------------
_QUERY_DB_DESC = (
    "Rulează SQL READ (SELECT/WITH) pe baza de date. Max 200 rânduri. "
    "Trebuie să incluzi `tenant_id = '<uuid>'` în WHERE. Tabelele de "
    "credențiale (api_keys, app_settings, *_tokens) sunt blocate."
)
_QUERY_DB_SCHEMA = {
    "type": "object",
    "properties": {"sql": {"type": "string", "description": "SELECT sau WITH."}},
    "required": ["sql"],
}

_PROPOSE_WRITE_DESC = (
    "Propune o modificare (INSERT/UPDATE/DELETE) — face dry-run, întoarce "
    "câte rânduri ar fi afectate și un TOKEN. NU modifică nimic încă. "
    "Cere CONFIRMAREA utilizatorului în chat înainte să cheme `execute_write`."
)
_PROPOSE_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {
            "type": "string",
            "description": "INSERT/UPDATE/DELETE. Trebuie cu tenant_id în WHERE.",
        }
    },
    "required": ["sql"],
}

_EXECUTE_WRITE_DESC = (
    "Execută o modificare propusă anterior cu `propose_write`. "
    "Apelează ASTA DOAR DUPĂ ce utilizatorul a confirmat explicit în chat."
)
_EXECUTE_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "token": {
            "type": "string",
            "description": "Token-ul primit de la propose_write.",
        }
    },
    "required": ["token"],
}


_GET_APP_VIEW_DESC = (
    "Apelează un VIEW al aplicației și întoarce EXACT ce afișează pagina UI "
    "corespunzătoare (cu logica de business completă — alocări de discount, "
    "dedup surse, monthly costs, etc.). Folosește acest tool când user-ul "
    "întreabă despre un meniu specific (ex. 'marja Aprilie 2026' → marja_lunara)."
)
_GET_APP_VIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "view_name": {
            "type": "string",
            "description": "Numele view-ului (vezi lista din system prompt).",
        },
        "params": {
            "type": "object",
            "description": "Parametri specifici view-ului (ex. scope, year, month).",
        },
    },
    "required": ["view_name"],
}


def _anthropic_tool(name: str, desc: str, schema: dict) -> dict:
    return {"name": name, "description": desc, "input_schema": schema}


def _openai_tool(name: str, desc: str, schema: dict) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": desc, "parameters": schema},
    }


_REMEMBER_DESC = (
    "Salvează o preferință / context persistent (cheie-valoare) la nivel de "
    "tenant. Se reîncarcă automat în prompt la conversații următoare."
)
_REMEMBER_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "value": {"type": "string"},
    },
    "required": ["key", "value"],
}
_FORGET_DESC = "Șterge o memorie persistentă după cheie."
_FORGET_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
}


# READ-ONLY: AI-ul are acces la TOATE datele dar nu poate modifica nimic.
# `propose_write` / `execute_write` au fost scoase intenționat.
ANTHROPIC_TOOLS: list[dict] = [
    _anthropic_tool("get_app_view", _GET_APP_VIEW_DESC, _GET_APP_VIEW_SCHEMA),
    _anthropic_tool("query_db", _QUERY_DB_DESC, _QUERY_DB_SCHEMA),
    _anthropic_tool("remember", _REMEMBER_DESC, _REMEMBER_SCHEMA),
    _anthropic_tool("forget", _FORGET_DESC, _FORGET_SCHEMA),
]

OPENAI_TOOLS: list[dict] = [
    _openai_tool("get_app_view", _GET_APP_VIEW_DESC, _GET_APP_VIEW_SCHEMA),
    _openai_tool("query_db", _QUERY_DB_DESC, _QUERY_DB_SCHEMA),
    _openai_tool("remember", _REMEMBER_DESC, _REMEMBER_SCHEMA),
    _openai_tool("forget", _FORGET_DESC, _FORGET_SCHEMA),
]


# Backwards-compat aliases (în caz că vreun cod vechi le mai importă).
QUERY_DB_TOOL_ANTHROPIC = ANTHROPIC_TOOLS[0]
QUERY_DB_TOOL_OPENAI = OPENAI_TOOLS[0]


# --------------------------------------------------------------------------
# Memorie persistentă (key-value tenant-wide)
# --------------------------------------------------------------------------
MEMORY_KEY_MAX = 100
MEMORY_VALUE_MAX = 5000


async def list_memories(session: AsyncSession, tenant_id: UUID) -> list[dict]:
    stmt = (
        select(AIMemory)
        .where(AIMemory.tenant_id == tenant_id, AIMemory.user_id.is_(None))
        .order_by(AIMemory.key)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [{"key": m.key, "value": m.value} for m in rows]


async def remember(
    session: AsyncSession, tenant_id: UUID, key: str, value: str
) -> dict:
    if not key or not key.strip():
        return {"error": "Cheie goală."}
    key = key.strip()
    if len(key) > MEMORY_KEY_MAX:
        return {"error": f"Cheia depășește {MEMORY_KEY_MAX} caractere."}
    if value is None:
        return {"error": "Valoare lipsă."}
    if len(value) > MEMORY_VALUE_MAX:
        return {"error": f"Valoarea depășește {MEMORY_VALUE_MAX} caractere."}

    stmt = select(AIMemory).where(
        AIMemory.tenant_id == tenant_id,
        AIMemory.user_id.is_(None),
        AIMemory.key == key,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        session.add(AIMemory(tenant_id=tenant_id, user_id=None, key=key, value=value))
        action = "saved"
    else:
        existing.value = value
        action = "updated"
    await session.commit()
    return {"ok": True, "action": action, "key": key}


async def forget(session: AsyncSession, tenant_id: UUID, key: str) -> dict:
    if not key or not key.strip():
        return {"error": "Cheie goală."}
    key = key.strip()
    stmt = select(AIMemory).where(
        AIMemory.tenant_id == tenant_id,
        AIMemory.user_id.is_(None),
        AIMemory.key == key,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return {"ok": False, "message": f"Nu există memorie cu cheia `{key}`."}
    await session.delete(existing)
    await session.commit()
    return {"ok": True, "key": key}


_REMEMBER_DESC = (
    "Salvează (sau actualizează) o informație persistentă tenant-wide. "
    "Exemple: anul implicit pentru rapoarte, scope preferat (adp/sika), "
    "convenții de afișare, terminologie specifică. Cheia trebuie să fie "
    "scurtă și descriptivă (ex: `default_year`, `report_format`). Memoria "
    "se încarcă automat la fiecare conversație nouă."
)
_REMEMBER_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {"type": "string", "description": "Cheia (max 100 caractere)."},
        "value": {"type": "string", "description": "Valoarea (max 5000 caractere)."},
    },
    "required": ["key", "value"],
}

_FORGET_DESC = (
    "Șterge o memorie persistentă după cheie. Folosește când utilizatorul "
    "spune explicit să uiți ceva."
)
_FORGET_SCHEMA = {
    "type": "object",
    "properties": {"key": {"type": "string"}},
    "required": ["key"],
}


# NOTE: definiția canonică a ANTHROPIC_TOOLS / OPENAI_TOOLS e mai sus (~ linia
# 343) și include get_app_view + read-only tools. Definiția veche (cu
# propose_write/execute_write) a fost scoasă intenționat — modul read-only.


async def dispatch_tool(
    session: AsyncSession,
    tenant_ids: list[UUID],
    name: str,
    args: dict,
) -> dict:
    """Rutează un tool call către implementarea corectă (READ-ONLY).

    Memoria persistentă e stocată pe primul tenant (= organizația default a
    user-ului) — partajată între SIKADP organizations.
    """
    primary_tenant = tenant_ids[0] if tenant_ids else None
    if name == "get_app_view":
        from app.modules.ai.app_views import get_app_view
        return await get_app_view(
            session, tenant_ids,
            view_name=args.get("view_name", ""),
            params=args.get("params") or {},
        )
    if name == "query_db":
        return await run_sql_readonly(session, tenant_ids, args.get("sql", ""))
    if name == "remember":
        if primary_tenant is None:
            return {"error": "Niciun tenant autorizat."}
        return await remember(
            session, primary_tenant, args.get("key", ""), args.get("value", "")
        )
    if name == "forget":
        if primary_tenant is None:
            return {"error": "Niciun tenant autorizat."}
        return await forget(session, primary_tenant, args.get("key", ""))
    if name in ("propose_write", "execute_write"):
        return {"error": "Modul read-only — modificările sunt dezactivate."}
    return {"error": f"Tool necunoscut: {name}"}
