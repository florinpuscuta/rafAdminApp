"""
Admin metrics endpoint — agregare slow queries + cache hit rate + AI cost
per tenant. Doar admin (get_current_admin).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.core.metrics import cache_metrics_snapshot, slow_query_stats
from app.modules.ai.models import AIUsageLog
from app.modules.auth.deps import get_current_admin
from app.modules.users.models import User

router = APIRouter(prefix="/api/admin/metrics", tags=["admin"])


@router.get("")
async def get_metrics(
    days: int = Query(7, ge=1, le=90, description="Fereastra pentru AI cost (zile)"),
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Snapshot agregat:
    - `slow_queries`: counters in-process (reset la pornire)
    - `cache`: hit/miss + hit_rate + per-prefix breakdown (din Redis)
    - `ai_cost`: tokens + cost USD per (tenant, model) în ultimele `days` zile
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(
            AIUsageLog.tenant_id,
            AIUsageLog.provider,
            AIUsageLog.model,
            func.count().label("calls"),
            func.coalesce(func.sum(AIUsageLog.input_tokens), 0).label("in_tok"),
            func.coalesce(func.sum(AIUsageLog.output_tokens), 0).label("out_tok"),
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0).label("cost_usd"),
            func.avg(AIUsageLog.latency_ms).label("avg_latency_ms"),
        )
        .where(AIUsageLog.created_at >= since)
        .group_by(AIUsageLog.tenant_id, AIUsageLog.provider, AIUsageLog.model)
        .order_by(func.sum(AIUsageLog.cost_usd).desc())
    )
    res = await session.execute(stmt)
    ai_rows = [
        {
            "tenant_id": str(r.tenant_id),
            "provider": r.provider,
            "model": r.model,
            "calls": int(r.calls),
            "input_tokens": int(r.in_tok),
            "output_tokens": int(r.out_tok),
            "cost_usd": float(r.cost_usd or Decimal(0)),
            "avg_latency_ms": float(r.avg_latency_ms) if r.avg_latency_ms else None,
        }
        for r in res.all()
    ]

    total_cost = sum(r["cost_usd"] for r in ai_rows)
    total_calls = sum(r["calls"] for r in ai_rows)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slow_queries": slow_query_stats.snapshot(),
        "cache": await cache_metrics_snapshot(),
        "ai_cost": {
            "window_days": days,
            "total_calls": total_calls,
            "total_cost_usd": round(total_cost, 6),
            "by_tenant_model": ai_rows,
        },
    }
