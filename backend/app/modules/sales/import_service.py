"""
Task async care rulează import-ul ADP cu progress tracking.

Rulează în background (asyncio.create_task) — creează propria session,
updatează job-ul via `jobs` module la fiecare etapă.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate_tenant as cache_invalidate_tenant
from app.core.db import SessionLocal
from app.modules.agents import service as agents_service
from app.modules.agents.models import Agent, AgentAlias, AgentStoreAssignment
from app.modules.audit import service as audit_service
from app.modules.products import service as products_service
from app.modules.sales import backfill as sales_backfill
from app.modules.sales import importer as sales_importer
from app.modules.sales import importer_sika as sales_importer_sika
from app.modules.sales import jobs
from app.modules.sales import service as sales_service
from app.modules.sales.models import RawSale
from app.modules.stores import service as stores_service
from app.modules.stores.models import Store, StoreAlias

logger = logging.getLogger("adeplast.sales.import")


_INSERT_CHUNK_SIZE = 5000


async def run_import_job(
    *,
    job_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    content: bytes,
    filename: str,
    full_reload: bool,
    source: str = "adp",
) -> None:
    """
    Entry-point — asyncio.create_task() apelează asta.
    `source`: 'adp' (default) sau 'sika'. Alege parser-ul și izolează deletes
    prin batch.source ('sales_xlsx' sau 'sika_xlsx').
    """
    try:
        await jobs.set_status(job_id, "running")
        async with SessionLocal() as session:
            result = await _run(
                session,
                job_id=job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                content=content,
                filename=filename,
                full_reload=full_reload,
                source=source,
            )
        await jobs.set_done(job_id, result)
    except _ImportAborted as e:
        await jobs.set_error(job_id, message=e.message, code=e.code)
    except Exception as e:  # pragma: no cover
        logger.exception("import job failed", extra={"job_id": str(job_id)})
        await jobs.set_error(job_id, message=str(e) or "Eroare internă", code="error")


class _ImportAborted(Exception):
    def __init__(self, message: str, code: str = "error"):
        self.message = message
        self.code = code
        super().__init__(message)


async def _run(
    session: AsyncSession,
    *,
    job_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    content: bytes,
    filename: str,
    full_reload: bool,
    source: str = "adp",
) -> dict[str, Any]:
    src_lower = source.lower()
    is_sika = src_lower in ("sika", "sika_mtd")
    is_mtd = src_lower == "sika_mtd"
    if is_mtd:
        batch_source = "sika_mtd_xlsx"
    elif is_sika:
        batch_source = "sika_xlsx"
    else:
        batch_source = "sales_xlsx"
    backfill_source = "SIKA" if is_sika else "ADP"

    # ── Stage 1: parse sheet principal ─────────────────────────────────
    if is_sika:
        rows, errors = sales_importer_sika.parse_xlsx(content)
    else:
        rows, errors = sales_importer.parse_xlsx(content)
    await jobs.finish_stage(job_id, "parse_main")

    if not rows and errors:
        raise _ImportAborted(
            message=errors[0] if errors else "Eroare de parsare",
            code="parse_error",
        )

    # ── Stage 2: parse Alocare (doar ADP — Sika n-are sheet Alocare) ──
    if is_sika:
        alocare_rows = []
    else:
        alocare_rows = sales_importer.parse_alocare_sheet(content)
    await jobs.finish_stage(job_id, "parse_alocare")

    # ── Stage 3: normalize canonicals din Alocare ─────────────────────
    alocare_summary: dict[str, int] = {
        "rows_processed": 0,
        "stores_created": 0,
        "store_aliases_created": 0,
        "agent_aliases_created": 0,
        "assignments_created": 0,
    }
    if alocare_rows:
        normalized = await _normalize_alocare(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            alocare_rows=alocare_rows,
            job_id=job_id,
        )
        alocare_summary = {"rows_processed": len(alocare_rows), **normalized}
    await jobs.finish_stage(job_id, "normalize")

    # ── Stage 4: ștergere rânduri conflictuale (scoped pe source) ─────
    # Pentru SIKA: istoricul (sika_xlsx) și MTD (sika_mtd_xlsx) pot acoperi
    # aceeași lună. Regula "la orice încărcare, luăm doar datele care lipsesc"
    # = fiecare upload îl înlocuiește pe celălalt pentru (year, month)
    # suprapuse. Șterg din AMBELE batch_source-uri pentru grupul SIKA.
    pairs = sorted({(r["year"], r["month"]) for r in rows})
    if is_sika:
        delete_scope_sources = ["sika_xlsx", "sika_mtd_xlsx"]
    else:
        delete_scope_sources = [batch_source]

    deleted = 0
    if full_reload:
        for src in delete_scope_sources:
            deleted += await sales_service.delete_all_raw_sales(
                session, tenant_id, batch_source=src,
            )
    else:
        for src in delete_scope_sources:
            deleted += await sales_service.delete_by_year_month_pairs(
                session, tenant_id, pairs, batch_source=src,
            )
    await jobs.finish_stage(job_id, "delete_old")

    # ── Stage 5: insert raw_sales (chunked, cu progres granular) ──────
    batch = await sales_service.create_batch(
        session,
        tenant_id=tenant_id,
        uploaded_by_user_id=user_id,
        filename=filename,
        source=batch_source,
    )

    unique_clients = list({r["client"] for r in rows})
    unique_agents = list({r["agent"] for r in rows if r.get("agent")})
    unique_codes = list({r["product_code"] for r in rows if r.get("product_code")})
    client_to_store = await stores_service.resolve_map(
        session, tenant_id, unique_clients
    )
    agent_to_canonical = await agents_service.resolve_map(
        session, tenant_id, unique_agents
    )
    code_to_product = await products_service.resolve_map(
        session, tenant_id, unique_codes
    )

    inserted = await _chunked_bulk_insert(
        session,
        tenant_id=tenant_id,
        batch_id=batch.id,
        rows=rows,
        client_to_store=client_to_store,
        agent_to_canonical=agent_to_canonical,
        code_to_product=code_to_product,
        job_id=job_id,
    )

    # ── Stage 6: finalize batch + backfill FK ─────────────────────────
    # finalize commit-uiește batch-ul; backfill rulează pe rânduri deja
    # vizibile și face propriul commit la final.
    await sales_service.finalize_batch(
        session, batch, inserted=inserted, skipped=len(errors)
    )
    backfill_result = await sales_backfill.run_full_backfill(
        session, tenant_id, resolved_by_user_id=user_id,
        source=backfill_source,
    )

    # ── Stage 6c: auto-apply Facturi Bonus de Asignat ─────────────
    # Regula KA (Leroy/Dedeman/Altex/Hornbach/Bricostore/Puskin + amount
    # sub threshold) se aplică automat după fiecare import ca să nu
    # reapară aceleași facturi la fiecare refresh de date. Deciziile
    # anterioare persistă pe cheia stabilă (tenant, year, month, client,
    # amount), deci regula rămâne "forever".
    try:
        from app.modules.evaluare_agenti import service as evaluare_service
        facturi_bonus_result = await evaluare_service.apply_facturi_bonus_rule_all(
            session, tenant_id, reason="auto_rule_on_import",
        )
        await session.commit()
    except Exception as exc:
        logger.exception("apply_facturi_bonus_rule_all failed: %s", exc)
        facturi_bonus_result = {"accepted": 0, "skipped": 0, "error": str(exc)[:200]}

    unmapped_clients = sum(1 for r in rows if r["client"] not in client_to_store)
    unmapped_agents = sum(
        1 for r in rows
        if r.get("agent") and r["agent"] not in agent_to_canonical
    )
    unmapped_products = sum(
        1 for r in rows
        if r.get("product_code") and r["product_code"] not in code_to_product
    )
    months_affected = [f"{y}-{m:02d}" for y, m in pairs]

    await audit_service.log_event(
        session,
        event_type="sales.batch_imported",
        tenant_id=tenant_id,
        user_id=user_id,
        target_type="import_batch",
        target_id=batch.id,
        metadata={
            "filename": filename,
            "inserted": inserted,
            "skipped": len(errors),
            "deleted": deleted,
            "full_reload": full_reload,
            "months_affected": months_affected,
            "alocare_rows": alocare_summary["rows_processed"],
            "backfill": str(backfill_result)[:500],
            "facturi_bonus_auto": str(facturi_bonus_result)[:300],
        },
    )
    await jobs.finish_stage(job_id, "finalize")

    # Invalidam cache-ul agregatelor pentru acest tenant — datele s-au schimbat.
    # Fail-soft: dacă Redis e jos, log + ignoră.
    try:
        deleted_keys = await cache_invalidate_tenant(tenant_id)
        if deleted_keys:
            logger.info(
                "cache invalidated for tenant=%s: %d keys", tenant_id, deleted_keys
            )
    except Exception as exc:
        logger.warning("cache invalidate after import failed: %s", exc)

    return {
        "inserted": inserted,
        "skipped": len(errors),
        "deleted_before_insert": deleted,
        "months_affected": months_affected,
        "unmapped_clients": unmapped_clients,
        "unmapped_agents": unmapped_agents,
        "unmapped_products": unmapped_products,
        "alocare": alocare_summary,
        "backfill": backfill_result,
        "errors": errors[:50],
    }


# ── Normalization Alocare ────────────────────────────────────────────────

async def _normalize_alocare(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    alocare_rows: list[dict[str, str]],
    job_id: UUID | None = None,
) -> dict[str, int]:
    from sqlalchemy import select

    created_stores = 0
    created_store_aliases = created_agent_aliases = created_assignments = 0

    existing_stores = (await session.execute(
        select(Store).where(Store.tenant_id == tenant_id)
    )).scalars().all()
    store_by_name = {s.name: s for s in existing_stores}

    existing_agents = (await session.execute(
        select(Agent).where(Agent.tenant_id == tenant_id)
    )).scalars().all()
    agent_by_name = {a.full_name: a for a in existing_agents}

    existing_store_aliases = (await session.execute(
        select(StoreAlias.raw_client).where(StoreAlias.tenant_id == tenant_id)
    )).scalars().all()
    store_alias_set = set(existing_store_aliases)

    existing_agent_aliases = (await session.execute(
        select(AgentAlias.raw_agent, AgentAlias.agent_id)
        .where(AgentAlias.tenant_id == tenant_id)
    )).all()
    agent_alias_map: dict[str, UUID] = {raw: aid for raw, aid in existing_agent_aliases}
    agent_by_id = {a.id: a for a in existing_agents}

    existing_assignments = (await session.execute(
        select(AgentStoreAssignment.agent_id, AgentStoreAssignment.store_id)
        .where(AgentStoreAssignment.tenant_id == tenant_id)
    )).all()
    assignment_set = {(a, s) for a, s in existing_assignments}

    # Strict mode: orice nume de agent din sheet-ul Alocare trebuie să existe
    # deja fie ca Agent.full_name (exact), fie ca AgentAlias.raw_agent. Altfel
    # abortăm — import-ul nu mai creează orbește agenți noi (sursa fantomelor).
    unknown_agents = sorted({
        row["agent_name"] for row in alocare_rows
        if row["agent_name"] not in agent_by_name
        and row["agent_name"] not in agent_alias_map
    })
    if unknown_agents:
        raise _ImportAborted(
            message=(
                "Nume de agenți necunoscute în sheet-ul Alocare: "
                + ", ".join(unknown_agents)
                + ". Adaugă-le ca alias (raw_agent → agent existent) sau "
                "creează agentul manual în UI înainte de re-import."
            ),
            code="unknown_agents",
        )

    total = len(alocare_rows)
    for idx, row in enumerate(alocare_rows, start=1):
        raw_client = row["raw_client"]
        raw_ship_to = row["raw_ship_to"]
        combined_key = row["combined_key"]
        agent_name = row["agent_name"]

        agent = agent_by_name.get(agent_name)
        if agent is None:
            alias_agent_id = agent_alias_map[agent_name]
            agent = agent_by_id[alias_agent_id]

        store = store_by_name.get(combined_key)
        if store is None:
            store = await stores_service.create_store(
                session, tenant_id=tenant_id,
                name=combined_key, chain=raw_client, city=raw_ship_to,
            )
            store_by_name[combined_key] = store
            created_stores += 1

        if combined_key not in store_alias_set:
            await stores_service.create_alias(
                session, tenant_id=tenant_id,
                raw_client=combined_key, store_id=store.id,
                resolved_by_user_id=user_id,
            )
            store_alias_set.add(combined_key)
            created_store_aliases += 1

        if agent_name not in agent_alias_map:
            await agents_service.create_alias(
                session, tenant_id=tenant_id,
                raw_agent=agent_name, agent_id=agent.id,
                resolved_by_user_id=user_id,
            )
            agent_alias_map[agent_name] = agent.id
            created_agent_aliases += 1

        assn_key = (agent.id, store.id)
        if assn_key not in assignment_set:
            session.add(AgentStoreAssignment(
                tenant_id=tenant_id, agent_id=agent.id, store_id=store.id,
            ))
            assignment_set.add(assn_key)
            created_assignments += 1

        if job_id is not None and (idx % 10 == 0 or idx == total):
            await jobs.update_stage(job_id, "normalize", idx / total * 100)

    await session.flush()
    return {
        "stores_created": created_stores,
        "store_aliases_created": created_store_aliases,
        "agent_aliases_created": created_agent_aliases,
        "assignments_created": created_assignments,
    }


# ── Chunked insert cu progres ────────────────────────────────────────────

async def _chunked_bulk_insert(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    batch_id: UUID,
    rows: list[dict[str, Any]],
    client_to_store: dict[str, UUID],
    agent_to_canonical: dict[str, UUID],
    code_to_product: dict[str, UUID],
    job_id: UUID,
) -> int:
    if not rows:
        return 0

    # Pre-fill FK resolution într-un singur pas (restul e doar SQL insert).
    prepared: list[dict[str, Any]] = []
    for row in rows:
        prepared.append({
            **row,
            "tenant_id": tenant_id,
            "batch_id": batch_id,
            "store_id": client_to_store.get(row["client"]),
            "agent_id": agent_to_canonical.get(row.get("agent") or ""),
            "product_id": code_to_product.get(row.get("product_code") or ""),
        })

    total = len(prepared)
    inserted = 0
    for start in range(0, total, _INSERT_CHUNK_SIZE):
        chunk = prepared[start : start + _INSERT_CHUNK_SIZE]
        await session.execute(RawSale.__table__.insert(), chunk)
        inserted += len(chunk)
        await jobs.update_stage(
            job_id, "insert", inserted / total * 100,
        )
    return inserted
