"""
Cache Redis pentru agregate grele (consolidat, marja_lunara).

Strategie:
- Singleton client async (redis.asyncio.Redis), creat lazy la prima utilizare.
- Decorator `@cached(prefix, ttl, key_fn)` pentru funcții async pure.
- Serializare JSON cu adaptor pentru `Decimal`, `UUID`, `datetime`, `date`,
  `set`, `frozenset`. Tipurile se reconstruiesc la deserializare după convenție:
    - chei "*_id", "*_ids" → UUID
    - chei numerice marker (sales_*, total*, diff, dose_*) → Decimal
    - chei "store_ids", "store_names" → set
- Fail-soft: orice eroare Redis e logată și funcția decorată rulează direct.
- Invalidare prin `invalidate_tenant(tenant_id)` — șterge toate cheile cu
  prefix `agg:*:{tenant_id}:*`. Apelat după import în `raw_sales`.

Setări (în `app.core.config.settings`):
- `redis_url` (default `redis://redis:6379/0`)
- `cache_ttl_aggregates` (default 3600s)
- `cache_enabled` (default True; setează False ca să dezactivezi peste tot)
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None
_disabled_until_restart = False  # set la True dacă connect-ul eșuează — evităm spam loguri


async def get_redis() -> aioredis.Redis | None:
    """
    Returnează clientul Redis singleton sau None dacă e dezactivat /
    indisponibil. Niciodată nu aruncă — fail-soft pentru caller.
    """
    global _client, _disabled_until_restart
    if not settings.cache_enabled or _disabled_until_restart:
        return None
    if _client is not None:
        return _client
    try:
        client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Validare conexiune — un PING; dacă pică, dezactivăm până la restart.
        await client.ping()
        _client = client
        return _client
    except Exception as exc:
        logger.warning(
            "Cache Redis indisponibil (%s) — continuăm fără cache.", exc
        )
        _disabled_until_restart = True
        return None


# ── Serializare JSON cu suport tipuri non-nativ ─────────────────────────────
class _JSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return {"__decimal__": str(obj)}
        if isinstance(obj, UUID):
            return {"__uuid__": str(obj)}
        if isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        if isinstance(obj, date):
            return {"__date__": obj.isoformat()}
        if isinstance(obj, (set, frozenset)):
            return {"__set__": list(obj)}
        return super().default(obj)


def _json_object_hook(obj: dict[str, Any]) -> Any:
    if "__decimal__" in obj:
        return Decimal(obj["__decimal__"])
    if "__uuid__" in obj:
        return UUID(obj["__uuid__"])
    if "__datetime__" in obj:
        return datetime.fromisoformat(obj["__datetime__"])
    if "__date__" in obj:
        return date.fromisoformat(obj["__date__"])
    if "__set__" in obj:
        # Reconstruim ca set — caller-ul știe că s-a salvat ca set.
        return set(obj["__set__"])
    return obj


def _dumps(value: Any) -> str:
    return json.dumps(value, cls=_JSONEncoder, separators=(",", ":"))


def _loads(s: str) -> Any:
    return json.loads(s, object_hook=_json_object_hook)


# ── Decorator principal ────────────────────────────────────────────────────
P = ParamSpec("P")
R = TypeVar("R")


def cached(
    prefix: str,
    *,
    key_fn: Callable[..., str],
    ttl: int | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator pentru funcții async pure (read-only). Cheia finală:
        agg:{prefix}:{key_fn(*args, **kwargs)}

    `key_fn` primește aceleași argumente ca funcția decorată și returnează
    string-ul ce identifică un rezultat unic (ex: tenant + perioadă + filtre).
    """
    effective_ttl = ttl if ttl is not None else settings.cache_ttl_aggregates

    def decorator(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            client = await get_redis()
            if client is None:
                return await fn(*args, **kwargs)

            try:
                key_suffix = key_fn(*args, **kwargs)
            except Exception as exc:
                logger.warning("cache key_fn a eșuat (%s) — bypass cache.", exc)
                return await fn(*args, **kwargs)

            full_key = f"agg:{prefix}:{key_suffix}"

            # GET
            try:
                raw = await client.get(full_key)
                if raw is not None:
                    return _loads(raw)  # type: ignore[return-value]
            except Exception as exc:
                logger.warning("cache GET a eșuat (%s) — fallback la DB.", exc)
                # Continuăm la calcul direct.

            # MISS — calculăm și salvăm
            result = await fn(*args, **kwargs)
            try:
                await client.setex(full_key, effective_ttl, _dumps(result))
            except Exception as exc:
                logger.warning("cache SET a eșuat (%s) — ignorat.", exc)

            return result

        return wrapper

    return decorator


# ── Decorator pentru funcții care returnează Pydantic models ───────────────
def cached_pydantic(
    prefix: str,
    *,
    key_fn: Callable[..., str],
    model: type,
    ttl: int | None = None,
) -> Callable[[Callable[P, Awaitable[Any]]], Callable[P, Awaitable[Any]]]:
    """
    Variantă a lui `cached` pentru funcții care returnează Pydantic v2 models.
    Serializează cu `model_dump_json()` și reconstruiește cu `model_validate_json()`,
    păstrând tipurile (Decimal, UUID etc.) corect.

    Args:
        prefix: prefix pentru cheie (ex: "marja_lunara").
        key_fn: callable care returnează sufixul cheii din args/kwargs.
        model: clasa Pydantic returnată (ex: `MarjaLunaraData`).
        ttl: TTL custom (default `cache_ttl_aggregates`).
    """
    effective_ttl = ttl if ttl is not None else settings.cache_ttl_aggregates

    def decorator(fn: Callable[P, Awaitable[Any]]) -> Callable[P, Awaitable[Any]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            client = await get_redis()
            if client is None:
                return await fn(*args, **kwargs)

            try:
                key_suffix = key_fn(*args, **kwargs)
            except Exception as exc:
                logger.warning("cache_pydantic key_fn a eșuat (%s).", exc)
                return await fn(*args, **kwargs)

            full_key = f"agg:{prefix}:{key_suffix}"

            try:
                raw = await client.get(full_key)
                if raw is not None:
                    return model.model_validate_json(raw)
            except Exception as exc:
                logger.warning("cache_pydantic GET a eșuat (%s).", exc)

            result = await fn(*args, **kwargs)
            try:
                payload = result.model_dump_json()
                await client.setex(full_key, effective_ttl, payload)
            except Exception as exc:
                logger.warning("cache_pydantic SET a eșuat (%s).", exc)

            return result

        return wrapper

    return decorator


# ── Invalidare ─────────────────────────────────────────────────────────────
async def invalidate_tenant(tenant_id: UUID | str) -> int:
    """
    Șterge toate cheile cu prefix `agg:*:{tenant_id}:*`. Returnează numărul
    de chei șterse. Folosit după import în `raw_sales` ca să nu serveze date
    stale. Fail-soft.
    """
    client = await get_redis()
    if client is None:
        return 0

    pattern = f"agg:*:{tenant_id}:*"
    deleted = 0
    try:
        # SCAN + DEL în batch-uri ca să nu blocăm Redis-ul cu KEYS.
        async for key in client.scan_iter(match=pattern, count=200):
            await client.delete(key)
            deleted += 1
    except Exception as exc:
        logger.warning("cache invalidate a eșuat (%s).", exc)
    return deleted


async def invalidate_all() -> int:
    """
    Șterge toate cheile `agg:*`. Folosit la nevoie pentru reset complet
    (ex: din endpoint admin / debug). Fail-soft.
    """
    client = await get_redis()
    if client is None:
        return 0
    deleted = 0
    try:
        async for key in client.scan_iter(match="agg:*", count=500):
            await client.delete(key)
            deleted += 1
    except Exception as exc:
        logger.warning("cache invalidate_all a eșuat (%s).", exc)
    return deleted


# ── Helper pentru build chei comune ────────────────────────────────────────
def months_csv(months: list[int]) -> str:
    """Helper: lista de luni → string canonic pentru chei."""
    return ",".join(str(m) for m in sorted(set(months)))
