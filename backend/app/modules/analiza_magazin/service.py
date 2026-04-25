"""
"Analiza Magazin" — gap de sortimentație pentru un magazin dintr-o rețea KA.

Pentru un magazin selectat (ex. "DEDEMAN BACĂU"), afișează produsele pe care
*rețeaua* le-a vândut în ultimele 3 luni dar pe care *magazinul* nu le-a
vândut în aceeași fereastră. Adică: „ce-ți lipsește din coș față de ce
lanțul cumpără pe ansamblu".

Reguli fixate:
  - fereastră: ultimele 3 luni cu date în tenant × scope (sliding cu datele,
    robust la lag de upload)
  - chain-uri acceptate: Dedeman / Altex / Leroy Merlin / Hornbach
    (magazinele ne-matching → "Alte" → ascunse din selector)
  - scope=adp  → batch source `sales_xlsx`; filtru categorie după
    `ProductCategory.code` (MU/EPS/UMEDE/DIBLURI/VARSACI etc.)
  - scope=sika → batch source `sika_mtd_xlsx` (prioritar) + `sika_xlsx`;
    filtru TM prin `classify_sika_tm(product.name)`
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.brands.models import Brand
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import ImportBatch, RawSale


MONTHS_WINDOW = 3
ALLOWED_MONTHS_WINDOWS: tuple[int, ...] = (3, 6, 9, 12)


_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]
_GROUPS_SIKA: list[list[str]] = [["sika_mtd_xlsx", "sika_xlsx"]]

# Categorii ADP care NU contează pentru analiza de sortimentație — paleți,
# var la saci, dibluri nu fac parte din oferta relevantă pentru KA.
_EXCLUDED_ADP_CATEGORIES: frozenset[str] = frozenset({"PALETI", "VARSACI", "DIBLURI"})


def _scope_sources(scope: str) -> list[list[str]]:
    if scope == "adp":
        return _GROUPS_ADP
    if scope == "sika":
        return _GROUPS_SIKA
    raise ValueError(f"Scope necunoscut: {scope}")


# Lanțurile KA acceptate (același set ca `marca_privata`, `mkt_facing`,
# `grupe_produse`). "Alte" e ascuns din selector.
KNOWN_CHAINS: tuple[str, ...] = ("Dedeman", "Altex", "Leroy Merlin", "Hornbach")


def _extract_chain(raw: str | None) -> str:
    if not raw:
        return "Alte"
    upper = raw.upper()
    if "DEDEMAN" in upper:
        return "Dedeman"
    if "ALTEX" in upper:
        return "Altex"
    if "LEROY" in upper or "MERLIN" in upper:
        return "Leroy Merlin"
    if "HORNBACH" in upper:
        return "Hornbach"
    return "Alte"


# ── fereastră 3 luni cu date ─────────────────────────────────────────────


async def _last_months_with_data(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    sources: list[str],
    months_window: int,
) -> list[tuple[int, int]]:
    """Ultimele `months_window` (year, month) cu date KA în tenant × surse."""
    if not sources:
        return []
    stmt = (
        select(RawSale.year, RawSale.month)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
        )
        .distinct()
        .order_by(RawSale.year.desc(), RawSale.month.desc())
        .limit(months_window)
    )
    rows = (await session.execute(stmt)).all()
    return [(int(r.year), int(r.month)) for r in rows]


def _ym_filter(pairs: list[tuple[int, int]]) -> tuple[set[int], set[int]]:
    """(years, months) pentru IN-uri SQL. Atenție: e un produs cartezian,
    acceptabil pentru ferestre mici (≤ 3 luni pe 1-2 ani)."""
    return {y for (y, _m) in pairs}, {m for (_y, m) in pairs}


# ── magazine (pentru selector) ───────────────────────────────────────────


@dataclass
class StoreOption:
    key: str          # RawSale.client
    chain: str
    agent: str | None = None  # agent dominant pentru magazin


async def list_stores(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    months_window: int = MONTHS_WINDOW,
) -> list[StoreOption]:
    """Magazinele din chain-uri cunoscute cu vânzări în fereastra dată."""
    groups = _scope_sources(scope)
    sources = [s for g in groups for s in g]
    pairs = await _last_months_with_data(
        session, tenant_id, sources=sources, months_window=months_window,
    )
    if not pairs:
        return []
    years, months = _ym_filter(pairs)

    # Agentul CURENT per magazin: agentul dominant (cel mai frecvent) din
    # rândurile `RawSale.agent_id` ale clientului în fereastra dată, rezolvat
    # la `Agent.full_name`. Folosim `agent_id` (resolvedul prin StoreAgentMapping),
    # NU textul din `RawSale.agent` — textul brut poate fi al persoanei care a
    # încărcat raportul, nu al agentului alocat magazinului.
    stmt = (
        select(
            RawSale.client,
            RawSale.agent_id,
            Agent.full_name,
            func.count().label("cnt"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .outerjoin(Agent, Agent.id == RawSale.agent_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
            RawSale.client.is_not(None),
        )
        .group_by(RawSale.client, RawSale.agent_id, Agent.full_name)
    )
    # Pereche (client, agent_id) cu cel mai mare cnt. agent_id NULL contează
    # doar ca fallback dacă nu există niciun rând cu agent rezolvat.
    best: dict[str, tuple[int, str | None]] = {}
    for r in (await session.execute(stmt)).all():
        name = str(r.client)
        agent_name = str(r.full_name) if r.full_name else None
        cnt = int(r.cnt or 0)
        prev = best.get(name)
        # Preferăm un agent rezolvat chiar și cu cnt mai mic decât None.
        if prev is None:
            best[name] = (cnt, agent_name)
        elif agent_name and (prev[1] is None or cnt > prev[0]):
            best[name] = (cnt, agent_name)

    out: list[StoreOption] = []
    for name, (_cnt, agent) in best.items():
        chain = _extract_chain(name)
        if chain == "Alte":
            continue
        out.append(StoreOption(key=name, chain=chain, agent=agent))
    # Ordonăm după chain (ordinea canonică) apoi alfabetic.
    chain_order = {c: i for i, c in enumerate(KNOWN_CHAINS)}
    out.sort(key=lambda s: (chain_order.get(s.chain, 99), s.key))
    return out


# ── gap ──────────────────────────────────────────────────────────────────


@dataclass
class GapProduct:
    product_id: UUID
    product_code: str
    product_name: str
    category: str | None
    chain_qty: Decimal
    chain_value: Decimal
    stores_selling_count: int


@dataclass
class CategoryBreakdown:
    category: str | None
    chain_sku_count: int
    own_sku_count: int
    gap_count: int


@dataclass
class GapResult:
    scope: str
    store: str
    chain: str
    months_window: int
    chain_sku_count: int
    own_sku_count: int
    gap: list[GapProduct]
    breakdown: list[CategoryBreakdown]


async def _chain_stores(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    chain: str,
    years: set[int],
    months: set[int],
    sources: list[str],
) -> list[str]:
    """Toate `RawSale.client` din `chain` cu date în fereastră."""
    stmt = (
        select(RawSale.client)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
            RawSale.client.is_not(None),
        )
        .distinct()
    )
    return [
        str(r.client)
        for r in (await session.execute(stmt)).all()
        if _extract_chain(str(r.client)) == chain
    ]


async def _chain_product_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    clients: list[str],
    years: set[int],
    months: set[int],
    sources: list[str],
) -> list[dict[str, Any]]:
    """Agregat (product_id, client) în fereastră — folosit ca să calculăm
    chain-totals + stores_selling_count dintr-un singur query."""
    if not clients:
        return []
    stmt = (
        select(
            RawSale.product_id,
            RawSale.client,
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
            RawSale.client.in_(clients),
            RawSale.product_id.is_not(None),
        )
        .group_by(RawSale.product_id, RawSale.client)
    )
    return [
        {
            "product_id": r.product_id,
            "client": str(r.client),
            "amount": Decimal(r.amt or 0),
            "quantity": Decimal(r.qty or 0),
        }
        for r in (await session.execute(stmt)).all()
    ]


async def _hydrate_products(
    session: AsyncSession,
    tenant_id: UUID,
    product_ids: set[UUID],
    *,
    scope: str,
) -> dict[UUID, tuple[str, str, str | None]]:
    """(code, name, category_label) pentru fiecare product_id.

    category_label:
      - adp  → ProductCategory.code (MU/EPS/UMEDE/...) sau None
      - sika → label TM via classify_sika_tm(name) sau None
    """
    if not product_ids:
        return {}
    if scope == "adp":
        rows = (await session.execute(
            select(
                Product.id, Product.code, Product.name,
                ProductCategory.code.label("cat_code"),
            )
            .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
            .where(
                Product.tenant_id == tenant_id,
                Product.id.in_(product_ids),
            )
        )).all()
        return {
            r.id: (r.code or "", r.name or "", r.cat_code)
            for r in rows
        }
    # sika — label TM derivat din nume
    from app.modules.grupe_produse.service import classify_sika_tm

    rows = (await session.execute(
        select(Product.id, Product.code, Product.name, Brand.name.label("brand"))
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .where(
            Product.tenant_id == tenant_id,
            Product.id.in_(product_ids),
        )
    )).all()
    out: dict[UUID, tuple[str, str, str | None]] = {}
    for r in rows:
        if r.brand != "Sika":
            # Produs non-Sika apărut cumva pe un batch Sika — lăsăm fără TM.
            out[r.id] = (r.code or "", r.name or "", None)
            continue
        tm = classify_sika_tm(r.name)
        out[r.id] = (r.code or "", r.name or "", tm if tm != "Altele" else None)
    return out


async def get_gap(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    store: str,
    months_window: int = MONTHS_WINDOW,
) -> GapResult | None:
    """Calculează gap-ul pentru `store`. Întoarce `None` dacă magazinul nu
    aparține unui chain cunoscut sau nu are date în fereastră."""
    chain = _extract_chain(store)
    if chain == "Alte":
        return None

    groups = _scope_sources(scope)
    sources = [s for g in groups for s in g]
    pairs = await _last_months_with_data(
        session, tenant_id, sources=sources, months_window=months_window,
    )
    if not pairs:
        return None
    years, months = _ym_filter(pairs)

    clients = await _chain_stores(
        session, tenant_id,
        chain=chain, years=years, months=months, sources=sources,
    )
    if not clients or store not in clients:
        return None

    rows = await _chain_product_rows(
        session, tenant_id,
        clients=clients, years=years, months=months, sources=sources,
    )

    # Agregat chain + identificat SKU-uri pe magazinul selectat.
    chain_agg: dict[UUID, dict[str, Any]] = {}
    own_skus: set[UUID] = set()
    for r in rows:
        pid: UUID = r["product_id"]
        client: str = r["client"]
        bucket = chain_agg.setdefault(pid, {
            "amount": Decimal(0),
            "quantity": Decimal(0),
            "stores": set(),
        })
        bucket["amount"] += r["amount"]
        bucket["quantity"] += r["quantity"]
        bucket["stores"].add(client)
        if client == store:
            own_skus.add(pid)

    chain_skus = set(chain_agg.keys())

    # Hidratăm TOATE SKU-urile lanțului (nu doar gap-ul) ca să avem categoria
    # pentru `own_skus` — necesară pentru breakdown-ul per categorie.
    meta = await _hydrate_products(session, tenant_id, chain_skus, scope=scope)

    # Excludem categoriile irelevante pentru ADP (paleți, var la saci, dibluri).
    if scope == "adp":
        drop = {
            pid for pid in chain_skus
            if meta.get(pid, ("", "", None))[2] in _EXCLUDED_ADP_CATEGORIES
        }
        if drop:
            chain_skus -= drop
            own_skus -= drop
            for pid in drop:
                chain_agg.pop(pid, None)

    gap_ids = chain_skus - own_skus

    gap: list[GapProduct] = []
    for pid in gap_ids:
        bucket = chain_agg[pid]
        code, name, category = meta.get(pid, ("", "", None))
        gap.append(GapProduct(
            product_id=pid,
            product_code=code,
            product_name=name,
            category=category,
            chain_qty=bucket["quantity"],
            chain_value=bucket["amount"],
            stores_selling_count=len(bucket["stores"]),
        ))

    gap.sort(key=lambda p: (-p.chain_value, p.product_name.lower()))

    # Breakdown per categorie peste tot chain_skus.
    bd_chain: dict[str | None, int] = {}
    bd_own: dict[str | None, int] = {}
    bd_gap: dict[str | None, int] = {}
    for pid in chain_skus:
        cat = meta.get(pid, ("", "", None))[2]
        bd_chain[cat] = bd_chain.get(cat, 0) + 1
        if pid in own_skus:
            bd_own[cat] = bd_own.get(cat, 0) + 1
        else:
            bd_gap[cat] = bd_gap.get(cat, 0) + 1
    # Ordonăm: întâi categoriile etichetate (alfabetic), apoi None.
    cats = sorted(
        bd_chain.keys(),
        key=lambda c: (c is None, (c or "").lower()),
    )
    breakdown = [
        CategoryBreakdown(
            category=c,
            chain_sku_count=bd_chain.get(c, 0),
            own_sku_count=bd_own.get(c, 0),
            gap_count=bd_gap.get(c, 0),
        )
        for c in cats
    ]

    return GapResult(
        scope=scope,
        store=store,
        chain=chain,
        months_window=months_window,
        chain_sku_count=len(chain_skus),
        own_sku_count=len(own_skus),
        gap=gap,
        breakdown=breakdown,
    )
