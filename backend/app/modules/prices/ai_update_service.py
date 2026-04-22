"""
AI Price Update Service — port 1:1 al legacy
`adeplast-dashboard/services/price_update_service.py`.

Folosește xAI Grok (live search nativ) pentru a găsi prețurile actuale ale
produselor pe site-urile Dedeman/Leroy/Hornbach/Brico și actualizează
celulele din `price_grid.brand_data` cu ai_status / ai_url / ai_reason /
ai_updated_at și `pret` nou.

Job async: rulează în background thread cu progress tracking în
`price_update_jobs` (Postgres).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg
import requests

# ── URL-urile de referință pentru fiecare rețea ─────────────────────────────
STORE_SITES: dict[str, str] = {
    "Dedeman":  "https://www.dedeman.ro",
    "Leroy":    "https://www.leroymerlin.ro",
    "Hornbach": "https://www.hornbach.ro",
    "Brico":    "https://www.bricodepot.ro",
}


def _pg_dsn_sync() -> str:
    """DSN sync pentru psycopg/asyncpg fără driver prefix."""
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


# ── AI call: Grok (xAI) cu live search ──────────────────────────────────────

def _build_lookup_prompt(product_name: str, brand: str, store: str) -> str:
    site_url = STORE_SITES.get(store, "")
    site_domain = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    return (
        f'Gaseste pretul (in RON cu TVA) pentru "{product_name}" brand {brand} pe {site_domain}.\n\n'
        f'Cauta pe Google: "{brand} {product_name} {site_domain} pret"\n'
        f'Accepta variante de denumire (ex: "AF-I" = "AFI", majuscule/spatii ignorate).\n'
        f'Daca Google arata pretul in snippet pentru acel domeniu, foloseste-l.\n\n'
        f'Raspunde DOAR JSON (fara markdown, fara text in jurul JSON-ului):\n'
        f'{{"found": true|false, "price": <numar>|null, "url": "<url>"|null, "reasoning": "<1 propozitie>"}}'
    )


def _parse_lookup_response(text: str) -> dict:
    """Parseaza raspunsul AI. Strategii: JSON direct, {...} embedded, regex fallback."""
    if not text:
        return {"found": False, "price": None, "url": None, "reasoning": "raspuns gol"}
    txt = text.strip()
    if "```" in txt:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.DOTALL)
        if m:
            txt = m.group(1)

    parsed = None
    try:
        parsed = json.loads(txt)
    except Exception:
        start = txt.find("{")
        end = txt.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(txt[start:end + 1])
            except Exception:
                parsed = None

    if isinstance(parsed, dict):
        found = bool(parsed.get("found"))
        price = parsed.get("price")
        if price is not None:
            try:
                price = float(price)
            except (ValueError, TypeError):
                price = None
        return {
            "found": found and price is not None,
            "price": price,
            "url": parsed.get("url"),
            "reasoning": (parsed.get("reasoning") or "")[:200],
        }

    # Fallback regex pe text liber
    pat_price = re.compile(
        r"(?:pre[tț]\s*[:=]?\s*|@\s*|la\s+)?"
        r"(\d{1,4}(?:[.,]\d{1,2})?)"
        r"\s*(?:RON|lei|Lei|LEI)",
        re.IGNORECASE,
    )
    m_price = pat_price.search(text)
    price = None
    if m_price:
        try:
            price = float(m_price.group(1).replace(",", "."))
        except (ValueError, TypeError):
            price = None
    m_url = re.search(r"https?://[^\s)\]'\"<>]+", text)
    url = m_url.group(0) if m_url else None
    if url:
        url = url.rstrip(".,;:!?)")

    found = price is not None and url is not None
    return {
        "found": found,
        "price": price,
        "url": url,
        "reasoning": (
            f"extras din text liber: pret={price} url={bool(url)}" if found
            else f"nu s-a putut extrage pret/URL din: {text[:150]}"
        ),
    }


def _lookup_price_anthropic(
    product_name: str, brand: str, store: str, api_key: str, timeout: int = 60,
) -> dict:
    """Anthropic Claude cu web_search tool."""
    prompt = _build_lookup_prompt(product_name, brand, store)
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "anthropic-beta": "web-search-2025-03-05",
            },
            json={
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 1500,
                "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return {
            "found": False, "price": None, "url": None,
            "reasoning": f"Anthropic err: {str(e)[:80]}",
        }
    text_block = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text_block = block.get("text", "")
    return _parse_lookup_response(text_block)


def _lookup_price_openai(
    product_name: str, brand: str, store: str, api_key: str, timeout: int = 60,
) -> dict:
    """OpenAI Chat Completions cu gpt-4o-search-preview."""
    prompt = _build_lookup_prompt(product_name, brand, store)
    max_attempts = 4
    backoff = 1.0
    last_err = None
    data = None
    for attempt in range(max_attempts):
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-search-preview",
                    "web_search_options": {},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=timeout,
            )
            if r.status_code == 429 and attempt < max_attempts - 1:
                ra = r.headers.get("Retry-After")
                try:
                    wait_s = float(ra) if ra else backoff
                except (TypeError, ValueError):
                    wait_s = backoff
                time.sleep(min(wait_s, 30))
                backoff *= 2
                last_err = f"429 (attempt {attempt + 1}/{max_attempts})"
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            last_err = str(e)[:80]
            if attempt >= max_attempts - 1:
                return {
                    "found": False, "price": None, "url": None,
                    "reasoning": f"OpenAI err: {last_err}",
                }
            time.sleep(backoff)
            backoff *= 2
    if data is None:
        return {
            "found": False, "price": None, "url": None,
            "reasoning": f"OpenAI err: {last_err}",
        }
    text_block = ""
    try:
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            text_block = msg.get("content", "") or ""
    except Exception:
        pass
    return _parse_lookup_response(text_block)


def _lookup_price_grok(
    product_name: str, brand: str, store: str, api_key: str, timeout: int = 60,
) -> dict:
    """xAI Grok cu live search. Model: grok-4-1-fast-reasoning."""
    site_url = STORE_SITES.get(store, "")
    domain = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    prompt = _build_lookup_prompt(product_name, brand, store)

    max_attempts = 4
    backoff = 1.0
    last_err = None
    data = None
    for attempt in range(max_attempts):
        try:
            r = requests.post(
                "https://api.x.ai/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-4-1-fast-reasoning",
                    "input": [{"role": "user", "content": prompt}],
                    "tools": [{
                        "type": "web_search",
                        "filters": {
                            "allowed_domains": [domain] if domain else [],
                        },
                    }],
                },
                timeout=timeout,
            )
            if r.status_code == 429 and attempt < max_attempts - 1:
                ra = r.headers.get("Retry-After")
                try:
                    wait_s = float(ra) if ra else backoff
                except (TypeError, ValueError):
                    wait_s = backoff
                time.sleep(min(wait_s, 30))
                backoff *= 2
                last_err = f"429 (attempt {attempt + 1}/{max_attempts})"
                continue
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            last_err = str(e)[:120]
            if attempt >= max_attempts - 1:
                return {
                    "found": False, "price": None, "url": None,
                    "reasoning": f"Grok err: {last_err}",
                }
            time.sleep(backoff)
            backoff *= 2
    if data is None:
        return {
            "found": False, "price": None, "url": None,
            "reasoning": f"Grok err: {last_err}",
        }

    # Responses API: output e listă de items; extragem textul din message blocks
    text_block = ""
    try:
        for item in data.get("output", []):
            itype = item.get("type", "")
            if itype == "message":
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text"):
                        text_block += c.get("text", "") or ""
            elif itype in ("output_text", "text"):
                text_block += item.get("text", "") or ""
        if not text_block:
            text_block = data.get("output_text", "") or ""
    except Exception:
        pass
    return _parse_lookup_response(text_block)


# ── Job state management (via direct asyncpg, sync wrappers pt thread) ──────

def _run_async(coro):
    """Helper pt a rula coroutine sincron dintr-un thread (pentru thread pool)."""
    return asyncio.run(coro)


async def _async_job_insert(tenant_id: UUID, job_id: str, company: str, store: str, total: int):
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        now = datetime.utcnow()
        await conn.execute(
            """INSERT INTO price_update_jobs
               (job_id, tenant_id, company, store, status, total,
                processed, found, not_found, errors, started_at)
               VALUES ($1,$2::uuid,$3,$4,'pending',$5,0,0,0,0,$6)""",
            job_id, str(tenant_id), company, store, total, now,
        )
    finally:
        await conn.close()


async def _async_job_set(job_id: str, **fields) -> None:
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        sets = ", ".join(f"{k}=${i+1}" for i, k in enumerate(fields))
        vals = list(fields.values())
        vals.append(job_id)
        await conn.execute(
            f"UPDATE price_update_jobs SET {sets} WHERE job_id=${len(vals)}",
            *vals,
        )
    finally:
        await conn.close()


async def _async_job_incr(job_id: str, **fields) -> None:
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        sets = ", ".join(f"{k}={k}+${i+1}" for i, k in enumerate(fields))
        vals = list(fields.values())
        vals.append(job_id)
        await conn.execute(
            f"UPDATE price_update_jobs SET {sets} WHERE job_id=${len(vals)}",
            *vals,
        )
    finally:
        await conn.close()


async def _async_job_get(job_id: str) -> dict | None:
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT * FROM price_update_jobs WHERE job_id=$1", job_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


def _job_set(job_id: str, **fields):
    _run_async(_async_job_set(job_id, **fields))


def _job_incr(job_id: str, **fields):
    _run_async(_async_job_incr(job_id, **fields))


def _job_get(job_id: str) -> dict | None:
    return _run_async(_async_job_get(job_id))


# ── Load cells + save lookup result (via asyncpg pt thread safety) ──────────

async def _async_load_cells(tenant_id: UUID, company: str, store: str) -> list[tuple[int, str, str]]:
    """Returnează [(row_idx, brand, prod)] pentru toate celulele non-goale."""
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """SELECT row_idx, brand_data FROM price_grid
               WHERE tenant_id=$1::uuid AND company=$2 AND store=$3
               ORDER BY row_idx""",
            str(tenant_id), company, store,
        )
        cells = []
        for r in rows:
            bd = r["brand_data"] or {}
            if isinstance(bd, str):
                try: bd = json.loads(bd)
                except Exception: bd = {}
            for brand, v in (bd or {}).items():
                prod = (v or {}).get("prod")
                if prod:
                    cells.append((r["row_idx"], brand, prod))
        return cells
    finally:
        await conn.close()


async def _async_save_lookup(
    tenant_id: UUID, company: str, store: str, row_idx: int, brand: str, result: dict,
):
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """SELECT id, brand_data FROM price_grid
               WHERE tenant_id=$1::uuid AND company=$2 AND store=$3 AND row_idx=$4""",
            str(tenant_id), company, store, row_idx,
        )
        if not row:
            return
        bd = row["brand_data"] or {}
        if isinstance(bd, str):
            try: bd = json.loads(bd)
            except Exception: bd = {}
        cell = bd.get(brand) or {}
        ai_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if result.get("found") and result.get("price") is not None:
            cell["pret"] = round(float(result["price"]), 2)
            cell["ai_status"] = "found"
            cell["ai_url"] = result.get("url")
            cell["ai_reason"] = result.get("reasoning") or ""
            cell["ai_updated_at"] = ai_ts
        else:
            cell["ai_status"] = "not_found"
            cell["ai_reason"] = result.get("reasoning") or ""
            cell["ai_updated_at"] = ai_ts
        bd[brand] = cell
        await conn.execute(
            "UPDATE price_grid SET brand_data=$1::jsonb WHERE id=$2",
            json.dumps(bd, ensure_ascii=False), row["id"],
        )
    finally:
        await conn.close()


# ── Public API (sync, pentru ca threading foloseste asta) ───────────────────

async def _get_provider_key_from_db(tenant_id: UUID, provider: str) -> str | None:
    """Citește cheia din app_settings (DB) pentru un tenant + provider."""
    key_name = "xai" if provider == "grok" else provider
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchval(
            "SELECT value FROM app_settings WHERE tenant_id=$1::uuid AND key=$2",
            str(tenant_id), f"ai_key_{key_name}",
        )
        return (row or "").strip() or None
    finally:
        await conn.close()


def _get_provider_key_from_env(provider: str) -> str | None:
    """Fallback: citește cheia din env."""
    if provider == "grok":
        k = (os.environ.get("XAI_API_KEY") or "").strip()
        return k if k and k.startswith("xai-") else None
    if provider == "anthropic":
        k = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        return k if k and k.startswith("sk-ant-") else None
    if provider == "openai":
        k = (os.environ.get("OPENAI_API_KEY") or "").strip()
        return k if k and k.startswith("sk-") else None
    return None


async def _get_provider_key(tenant_id: UUID, provider: str) -> str | None:
    """DB first, env fallback."""
    k = await _get_provider_key_from_db(tenant_id, provider)
    if k:
        return k
    return _get_provider_key_from_env(provider)


async def _select_ai_provider(
    tenant_id: UUID, preferred: str | None = None,
) -> tuple[str | None, str | None]:
    """Alege provider-ul AI pentru un tenant. Preferință:
      1. `preferred` dacă e specificat și are cheie (în DB sau env)
      2. xAI Grok (live search nativ)
      3. Anthropic Claude
      4. OpenAI ChatGPT
    """
    if preferred:
        k = await _get_provider_key(tenant_id, preferred)
        if k:
            return k, preferred

    for p in ("grok", "anthropic", "openai"):
        k = await _get_provider_key(tenant_id, p)
        if k:
            return k, p
    return None, None


def _lookup_price_via_ai(
    product_name: str, brand: str, store: str, api_key: str,
    timeout: int = 60, provider: str = "grok",
) -> dict:
    """Dispatcher pentru provider."""
    if provider == "anthropic":
        return _lookup_price_anthropic(product_name, brand, store, api_key, timeout)
    if provider == "openai":
        return _lookup_price_openai(product_name, brand, store, api_key, timeout)
    return _lookup_price_grok(product_name, brand, store, api_key, timeout)


async def get_active_job(tenant_id: UUID, store: str, company: str = "adeplast") -> dict | None:
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """SELECT * FROM price_update_jobs
               WHERE tenant_id=$1::uuid AND store=$2 AND company=$3
                 AND status IN ('pending','running')
               ORDER BY started_at DESC LIMIT 1""",
            str(tenant_id), store, company,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_latest_job(tenant_id: UUID, store: str, company: str = "adeplast") -> dict | None:
    dsn = _pg_dsn_sync()
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """SELECT * FROM price_update_jobs
               WHERE tenant_id=$1::uuid AND store=$2 AND company=$3
               ORDER BY started_at DESC LIMIT 1""",
            str(tenant_id), store, company,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def cancel_job(job_id: str) -> None:
    await _async_job_set(job_id, status="cancelled", finished_at=datetime.utcnow())


async def start_update_job(
    tenant_id: UUID, store: str, company: str = "adeplast",
    force: bool = False, preferred_provider: str | None = None,
) -> tuple[str, int, str]:
    """Pornește un job în background thread. Returnează (job_id, total, provider)."""
    if not force:
        active = await get_active_job(tenant_id, store, company)
        if active:
            raise RuntimeError(
                f"exista deja un job activ pentru {company}/{store}: {active['job_id']}"
            )
    api_key, provider = await _select_ai_provider(tenant_id, preferred=preferred_provider)
    if not api_key:
        raise RuntimeError(
            "Lipsește cheia AI. Setează una: XAI_API_KEY (xai-...), "
            "ANTHROPIC_API_KEY (sk-ant-...) sau OPENAI_API_KEY (sk-...)."
        )

    cells = await _async_load_cells(tenant_id, company, store)
    total = len(cells)
    job_id = uuid4().hex[:16]
    await _async_job_insert(tenant_id, job_id, company, store, total)
    await _async_job_set(job_id, provider=provider)

    t = threading.Thread(
        target=_run_job,
        args=(job_id, tenant_id, store, company, cells, api_key, provider),
        daemon=False,
        name=f"price_update_{company}_{store}_{job_id}",
    )
    t.start()
    return job_id, total, provider


def _run_job(
    job_id: str, tenant_id: UUID, store: str, company: str,
    cells: list, api_key: str, provider: str,
):
    """Worker thread — rulează AI lookups în paralel cu ThreadPoolExecutor."""
    _job_set(job_id, status="running")
    MAX_WORKERS = 5

    def _process_one(row_idx: int, brand: str, prod: str):
        current = _job_get(job_id)
        if not current or current.get("status") == "cancelled":
            return
        try:
            result = _lookup_price_via_ai(
                prod, brand, store, api_key, provider=provider,
            )
            _run_async(_async_save_lookup(tenant_id, company, store, row_idx, brand, result))
            if result.get("found"):
                _job_incr(job_id, processed=1, found=1)
            else:
                _job_incr(job_id, processed=1, not_found=1)
        except Exception as e:
            _job_incr(job_id, processed=1, errors=1)
            _run_async(_async_save_lookup(
                tenant_id, company, store, row_idx, brand,
                {"found": False, "price": None, "url": None,
                 "reasoning": f"eroare: {str(e)[:80]}"},
            ))

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [
                ex.submit(_process_one, row_idx, brand, prod)
                for row_idx, brand, prod in cells
            ]
            for _ in as_completed(futures):
                pass
        _job_set(job_id, status="done", finished_at=datetime.utcnow())
    except Exception as e:
        _job_set(
            job_id, status="failed", error_msg=str(e)[:200],
            finished_at=datetime.utcnow(),
        )


async def get_job_progress(job_id: str) -> dict | None:
    return await _async_job_get(job_id)
