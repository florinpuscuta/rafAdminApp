"""
Modul de metrici operaționale.

Colectează 3 categorii:
1. **Slow queries** — counter in-process + warning log + Sentry capture la
   threshold mare. Hook-uit pe SQLAlchemy `before_cursor_execute` /
   `after_cursor_execute`.
2. **Cache hit/miss** — counter persistent în Redis (`metrics:cache:hits|misses`).
3. **AI usage / cost** — citit din tabelul `ai_usage_log` (vezi
   `app.modules.ai.usage`).

Expus prin endpoint admin în `app.modules.admin_metrics.router`.
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from threading import Lock
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger("adeplast.metrics")


# ── Counters in-process pentru slow queries ────────────────────────────────
class _SlowQueryStats:
    """Counters thread-safe pentru queries lente. Reset la repornirea procesului."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.total_queries: int = 0
        self.slow_queries: int = 0
        self.slowest_ms: float = 0.0
        self.slowest_sample: str = ""
        # Top-5 sloweste vizibile in /metrics ca sample (deduplicate dupa primul N
        # caractere ale SQL-ului).
        self._top: list[tuple[float, str]] = []
        self._top_max = 5

    def record(self, duration_ms: float, sql: str) -> None:
        with self._lock:
            self.total_queries += 1
            if duration_ms < settings.slow_query_threshold_ms:
                return
            self.slow_queries += 1
            short = sql.strip().replace("\n", " ")[:200]
            if duration_ms > self.slowest_ms:
                self.slowest_ms = duration_ms
                self.slowest_sample = short
            # Top-N
            self._top.append((duration_ms, short))
            self._top.sort(key=lambda t: t[0], reverse=True)
            del self._top[self._top_max:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            ratio = (
                round(self.slow_queries / self.total_queries * 100, 2)
                if self.total_queries
                else 0.0
            )
            return {
                "total_queries": self.total_queries,
                "slow_queries": self.slow_queries,
                "slow_pct": ratio,
                "threshold_ms": settings.slow_query_threshold_ms,
                "slowest_ms": round(self.slowest_ms, 2),
                "slowest_sample": self.slowest_sample,
                "top": [{"duration_ms": round(d, 2), "sql": s} for d, s in self._top],
            }


slow_query_stats = _SlowQueryStats()


# ── SQLAlchemy listeners ───────────────────────────────────────────────────
def install_slow_query_listener(sync_engine: Engine) -> None:
    """Atașează event listenerii pe engine-ul SYNC (pentru AsyncEngine,
    pasează `engine.sync_engine`).

    Strategie: marcăm timpul în `before_cursor_execute` pe `conn.info`
    (per-connection state), citim diferența în `after_cursor_execute`.
    """

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(  # type: ignore[no-redef]
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("_query_start_stack", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(  # type: ignore[no-redef]
        conn, cursor, statement, parameters, context, executemany
    ):
        stack = conn.info.get("_query_start_stack")
        if not stack:
            return
        start = stack.pop()
        duration_ms = (time.perf_counter() - start) * 1000.0
        slow_query_stats.record(duration_ms, statement)
        if duration_ms >= settings.slow_query_threshold_ms:
            short_sql = statement.strip().replace("\n", " ")[:300]
            logger.warning(
                "slow_query duration_ms=%.1f sql=%s", duration_ms, short_sql
            )
            # Sentry capture la threshold mai mare ca să nu spammuim.
            if duration_ms >= settings.sentry_slow_query_threshold_ms:
                try:
                    import sentry_sdk

                    sentry_sdk.capture_message(
                        f"Slow query {duration_ms:.0f}ms",
                        level="warning",
                        extras={"sql": short_sql, "duration_ms": duration_ms},
                    )
                except Exception:
                    pass  # Sentry inactiv sau eroare de raportare — ignorăm


# ── Cache metrics (counters Redis persistent) ──────────────────────────────
async def cache_hit(prefix: str) -> None:
    """Increment hit counter — fail-soft."""
    from app.core.cache import get_redis

    client = await get_redis()
    if client is None:
        return
    try:
        pipe = client.pipeline()
        pipe.incr("metrics:cache:hits:total")
        pipe.incr(f"metrics:cache:hits:by_prefix:{prefix}")
        await pipe.execute()
    except Exception:
        pass


async def cache_miss(prefix: str) -> None:
    """Increment miss counter — fail-soft."""
    from app.core.cache import get_redis

    client = await get_redis()
    if client is None:
        return
    try:
        pipe = client.pipeline()
        pipe.incr("metrics:cache:misses:total")
        pipe.incr(f"metrics:cache:misses:by_prefix:{prefix}")
        await pipe.execute()
    except Exception:
        pass


async def cache_metrics_snapshot() -> dict[str, Any]:
    """Citește toate contoarele cache din Redis. Fail-soft — dacă Redis e jos,
    întoarce zero-uri."""
    from app.core.cache import get_redis

    client = await get_redis()
    if client is None:
        return {"available": False, "hits": 0, "misses": 0, "hit_rate_pct": 0.0}

    try:
        hits = int(await client.get("metrics:cache:hits:total") or 0)
        misses = int(await client.get("metrics:cache:misses:total") or 0)
        # Per-prefix breakdown.
        per_prefix: dict[str, dict[str, int]] = {}
        async for key in client.scan_iter(
            match="metrics:cache:hits:by_prefix:*", count=100
        ):
            prefix = key.split(":", 4)[-1]
            per_prefix.setdefault(prefix, {"hits": 0, "misses": 0})
            per_prefix[prefix]["hits"] = int(await client.get(key) or 0)
        async for key in client.scan_iter(
            match="metrics:cache:misses:by_prefix:*", count=100
        ):
            prefix = key.split(":", 4)[-1]
            per_prefix.setdefault(prefix, {"hits": 0, "misses": 0})
            per_prefix[prefix]["misses"] = int(await client.get(key) or 0)
        for p, d in per_prefix.items():
            t = d["hits"] + d["misses"]
            d["hit_rate_pct"] = round(d["hits"] / t * 100, 2) if t else 0.0

        total = hits + misses
        rate = round(hits / total * 100, 2) if total else 0.0
        return {
            "available": True,
            "hits": hits,
            "misses": misses,
            "hit_rate_pct": rate,
            "by_prefix": per_prefix,
        }
    except Exception as exc:
        logger.warning("cache_metrics_snapshot failed: %s", exc)
        return {"available": False, "hits": 0, "misses": 0, "hit_rate_pct": 0.0}


async def reset_cache_metrics() -> None:
    """Pentru debug / testing. Șterge toate contoarele `metrics:cache:*`."""
    from app.core.cache import get_redis

    client = await get_redis()
    if client is None:
        return
    try:
        async for key in client.scan_iter(match="metrics:cache:*", count=200):
            await client.delete(key)
    except Exception:
        pass
