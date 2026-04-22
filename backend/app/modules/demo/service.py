"""
Demo data seeder — populează un tenant gol cu date sintetice pentru ca
adminul să poată explora feature-urile înainte să importe date reale.

Datele sunt deterministic-random (seed fix) ca să fie reproductibile și să
nu producă rezultate surprinzătoare.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activitate.models import AgentVisit
from app.modules.agents.models import Agent, AgentAlias, AgentStoreAssignment
from app.modules.brands.models import Brand, BrandAlias
from app.modules.parcurs.models import (
    TravelSheet,
    TravelSheetEntry,
    TravelSheetFuelFill,
)
from app.modules.probleme.models import ActivityProblem
from app.modules.product_categories.models import (
    ProductCategory,
    ProductCategoryAlias,
)
from app.modules.products.models import Product, ProductAlias
from app.modules.sales.models import ImportBatch, RawSale
from app.modules.stores.models import Store, StoreAlias


# ── Catalog sintetic realist pentru Adeplast KA ─────────────────────────────
_STORE_SEEDS = [
    ("Dedeman Bucuresti Pipera", "Dedeman", "Bucuresti"),
    ("Dedeman Cluj Napoca Centru", "Dedeman", "Cluj Napoca"),
    ("Dedeman Timisoara Nord", "Dedeman", "Timisoara"),
    ("Hornbach Bucuresti Militari", "Hornbach", "Bucuresti"),
    ("Leroy Merlin Iasi", "Leroy Merlin", "Iasi"),
    ("Brico Depot Constanta", "Brico Depot", "Constanta"),
    ("Praktiker Brasov", "Praktiker", "Brasov"),
]

_AGENT_SEEDS = [
    ("Ionut Filip", "ionut.filip@example.com"),
    ("Maria Popescu", "maria.popescu@example.com"),
    ("Andrei Ionescu", "andrei.ionescu@example.com"),
    ("Cristina Radu", "cristina.radu@example.com"),
    ("Bogdan Dumitrescu", "bogdan.d@example.com"),
]

_PRODUCT_SEEDS = [
    # Category-urile replică taxonomia Adeplast din app-ul legacy:
    # MU=Mortare Uscate, EPS=Polistiren, UMEDE=Adezivi Umezi, VARSACI=Vrac.
    ("ADZ-001", "Adeziv Placi Ceramice 25kg", "UMEDE", "Adeplast"),
    ("ADZ-002", "Adeziv Gresie Exterior 25kg", "UMEDE", "Adeplast"),
    ("TNC-001", "Tencuiala Decorativa Alba 25kg", "MU", "Adeplast"),
    ("TNC-002", "Tencuiala Mozaicata 25kg", "MU", "Adeplast"),
    ("SAP-001", "Sapa Autonivelanta 25kg", "MU", "Adeplast"),
    ("SAP-002", "Sapa Rapida 25kg", "MU", "Adeplast"),
    ("GIP-001", "Gips Carton Standard", "MU", "Adeplast"),
    ("EPS-001", "Polistiren EPS 80 5cm", "EPS", "Adeplast"),
    ("EPS-002", "Polistiren EPS 100 10cm", "EPS", "Adeplast"),
    ("EPS-003", "Polistiren EPS 70 8cm", "EPS", "Adeplast"),
    ("MOR-001", "Mortar Zidarie M10", "MU", "Adeplast"),
    ("MOR-002", "Mortar Vrac Silozuri MTI", "VARSACI", "Adeplast"),
]


async def _has_data(session: AsyncSession, tenant_id: UUID) -> bool:
    """Check dacă tenantul are deja vreo entitate canonică sau vânzări."""
    for model in (Store, Agent, Product, RawSale):
        count = (
            await session.execute(
                select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
            )
        ).scalar_one()
        if count and count > 0:
            return True
    return False


async def seed_demo_data(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> dict[str, int]:
    """
    Creează un set complet de date sintetice: stores, agents, products,
    alias-uri, assignments, un import batch + ~500 raw_sales pe 12 luni.

    Raises ValueError("not_empty") dacă tenantul are deja date — previne
    suprascrierea accidentală.
    """
    if await _has_data(session, tenant_id):
        raise ValueError("not_empty")

    rng = random.Random(42)  # seed fix pentru reproductibilitate

    # 1) Stores + aliases
    stores: list[Store] = []
    for name, chain, city in _STORE_SEEDS:
        s = Store(tenant_id=tenant_id, name=name, chain=chain, city=city)
        session.add(s)
        stores.append(s)
    await session.flush()

    # Alias-uri: 2 per store, simulează variații din Excel-ul original
    for s in stores:
        for variant_idx in range(2):
            raw = f"{s.name.upper()}" if variant_idx == 0 else f"{s.chain.upper()} {s.city.upper()}"
            session.add(StoreAlias(
                tenant_id=tenant_id,
                raw_client=f"{raw} #{variant_idx}",  # unic
                store_id=s.id,
                resolved_by_user_id=user_id,
            ))

    # 2) Agents + aliases
    agents: list[Agent] = []
    for full_name, email in _AGENT_SEEDS:
        a = Agent(tenant_id=tenant_id, full_name=full_name, email=email, active=True)
        session.add(a)
        agents.append(a)
    await session.flush()

    for a in agents:
        session.add(AgentAlias(
            tenant_id=tenant_id,
            raw_agent=a.full_name.upper(),
            agent_id=a.id,
            resolved_by_user_id=user_id,
        ))

    # 3) Categorii globale (deja seedate la migration) — lookup code → id.
    cat_rows = (
        await session.execute(select(ProductCategory))
    ).scalars().all()
    cat_id_by_code: dict[str, UUID] = {c.code: c.id for c in cat_rows}

    # 3.1) Alias-uri categorii pentru tenant (raw-string din Excel → global id).
    # Simulăm variantele pe care le-am vedea în import-uri reale.
    category_alias_seeds = [
        ("EPS", "EPS"), ("POLISTIREN", "EPS"), ("Eps Detalii", "EPS"),
        ("MU", "MU"), ("MORTARE USCATE", "MU"),
        ("UMEDE", "UMEDE"), ("ADEZIVI UMEZI", "UMEDE"),
        ("VARSACI", "VARSACI"), ("VRAC", "VARSACI"),
    ]
    for raw, code in category_alias_seeds:
        if code in cat_id_by_code:
            session.add(ProductCategoryAlias(
                tenant_id=tenant_id,
                raw_value=raw,
                category_id=cat_id_by_code[code],
                resolved_by_user_id=user_id,
            ))

    # 3.2) Brands (tenant-scoped) — un brand principal "Adeplast" + exemplu
    # private label ca să avem flag-ul is_private_label populat.
    brand_seeds = [
        ("Adeplast", False, 10),
        ("Baumit", False, 20),
        ("Hornbach Private Label", True, 30),
    ]
    brand_id_by_name: dict[str, UUID] = {}
    for name, is_pl, sort in brand_seeds:
        b = Brand(
            tenant_id=tenant_id,
            name=name,
            is_private_label=is_pl,
            sort_order=sort,
        )
        session.add(b)
        await session.flush()
        brand_id_by_name[name] = b.id
        # Un alias trivial (raw UPPER) pentru simulare.
        session.add(BrandAlias(
            tenant_id=tenant_id,
            raw_value=name.upper(),
            brand_id=b.id,
            resolved_by_user_id=user_id,
        ))

    # 3.3) Products — populez AT și string-urile legacy, ȘI FK-urile canonice.
    products: list[Product] = []
    for code, name, category_code, brand_name in _PRODUCT_SEEDS:
        p = Product(
            tenant_id=tenant_id,
            code=code,
            name=name,
            category=category_code,  # string legacy (safety)
            brand=brand_name,          # string legacy (safety)
            category_id=cat_id_by_code.get(category_code),
            brand_id=brand_id_by_name.get(brand_name),
        )
        session.add(p)
        products.append(p)
    await session.flush()

    for p in products:
        session.add(ProductAlias(
            tenant_id=tenant_id,
            raw_code=f"RAW-{p.code}",
            product_id=p.id,
            resolved_by_user_id=user_id,
        ))

    # 4) Assignments — fiecare agent acoperă 2-3 magazine random
    for a in agents:
        for s in rng.sample(stores, k=rng.randint(2, 3)):
            session.add(AgentStoreAssignment(
                tenant_id=tenant_id, agent_id=a.id, store_id=s.id,
            ))

    # 5) Import batch + raw_sales
    now = datetime.now(timezone.utc)
    batch = ImportBatch(
        tenant_id=tenant_id,
        uploaded_by_user_id=user_id,
        filename="demo-data.xlsx",
        source="demo_seed",
        inserted_rows=0,
        skipped_rows=0,
    )
    session.add(batch)
    await session.flush()

    current_year = now.year
    current_month = now.month
    sales_rows = 0
    for month_offset in range(12):
        m = current_month - month_offset
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        # ~40-50 linii per lună distribuite aleator pe combinații valide
        for _ in range(rng.randint(40, 50)):
            s = rng.choice(stores)
            a = rng.choice(agents)
            p = rng.choice(products)
            amount = Decimal(str(round(rng.uniform(150, 8000), 2)))
            qty = Decimal(str(round(rng.uniform(1, 50), 3)))
            session.add(RawSale(
                tenant_id=tenant_id,
                batch_id=batch.id,
                year=y,
                month=m,
                client=s.name.upper(),
                channel=rng.choice(["retail", "KA", "dist"]),
                product_code=f"RAW-{p.code}",
                product_name=p.name,
                category_code=p.category,
                amount=amount,
                quantity=qty,
                agent=a.full_name.upper(),
                store_id=s.id,
                agent_id=a.id,
                product_id=p.id,
            ))
            sales_rows += 1

    batch.inserted_rows = sales_rows

    # 6) Activitate — ~50 vizite distribuite pe ultimele 60 zile
    from datetime import date as _date, timedelta as _td
    visits_count = 0
    today = _date.today()
    for _ in range(50):
        day_offset = rng.randint(0, 60)
        visit_date = today - _td(days=day_offset)
        if visit_date.weekday() >= 5:
            continue  # doar zile lucrătoare
        a = rng.choice(agents)
        s = rng.choice(stores)
        ci_h = rng.randint(8, 15)
        ci_m = rng.choice([0, 15, 30, 45])
        dur = rng.randint(25, 90)
        co_total = ci_h * 60 + ci_m + dur
        co_h, co_m = divmod(co_total, 60)
        session.add(AgentVisit(
            tenant_id=tenant_id,
            scope="adp",
            visit_date=visit_date,
            agent_id=a.id,
            store_id=s.id,
            client=s.name.upper(),
            check_in=f"{ci_h:02d}:{ci_m:02d}",
            check_out=f"{co_h:02d}:{co_m:02d}",
            duration_min=dur,
            km=Decimal(str(rng.randint(15, 120))),
            notes=rng.choice([None, None, "Verificare stoc", "Negociere contract", "Follow-up reclamatie"]),
            created_by_user_id=user_id,
        ))
        visits_count += 1

    # 7) Probleme — câte o intrare pentru ultimele 3 luni, scope adp
    probleme_count = 0
    sample_problems = [
        "Întârzieri livrări zona Moldova — 2 săptămâni.\nReclamații calitate ciment vrac.",
        "Stoc limitat adezivi umezi în Oradea.\nConcurență agresivă Baumit pe KA.",
        "Transport blocat — probleme administrative vamă.\nDedeman Cluj solicită reduceri suplimentare.",
    ]
    for offset, text in enumerate(sample_problems):
        m = current_month - offset
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
        session.add(ActivityProblem(
            tenant_id=tenant_id,
            scope="adp",
            year=y,
            month=m,
            content=text,
            updated_by="demo@adeplast-saas.local",
            updated_by_user_id=user_id,
        ))
        probleme_count += 1

    # 8) Parcurs — o foaie exemplu pentru primul agent, luna curentă
    sheets_count = 0
    if agents:
        a = agents[0]
        wd = []
        import calendar as _cal
        for d in range(1, _cal.monthrange(current_year, current_month)[1] + 1):
            dd = _date(current_year, current_month, d)
            if dd.weekday() < 5:
                wd.append(dd)
        num_days = len(wd) or 1
        total_km = 2400
        sheet = TravelSheet(
            tenant_id=tenant_id,
            scope="adp",
            agent_id=a.id,
            agent_name=a.full_name,
            year=current_year,
            month=current_month,
            car_number="BH 12 DEM",
            sediu="Oradea",
            km_start=50000,
            km_end=50000 + total_km,
            total_km=total_km,
            working_days=num_days,
            avg_km_per_day=Decimal(total_km) / Decimal(num_days),
            total_fuel_liters=Decimal("180"),
            total_fuel_cost=Decimal("1200"),
            ai_generated=False,
            created_by_user_id=user_id,
        )
        session.add(sheet)
        await session.flush()
        cur = 50000
        per_day = total_km // num_days
        day_names = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]
        for d in wd:
            session.add(TravelSheetEntry(
                sheet_id=sheet.id,
                entry_date=d,
                day_name=day_names[d.weekday()],
                route="Oradea → Teren → Oradea",
                stores_visited=None,
                km_start=cur,
                km_end=cur + per_day,
                km_driven=per_day,
                purpose="Vizită comercială",
                fuel_liters=None,
                fuel_cost=None,
            ))
            cur += per_day
        session.add(TravelSheetFuelFill(
            sheet_id=sheet.id,
            fill_date=wd[0] if wd else _date(current_year, current_month, 1),
            liters=Decimal("90"),
            cost=Decimal("600"),
        ))
        sheets_count += 1

    await session.commit()

    return {
        "stores": len(stores),
        "agents": len(agents),
        "products": len(products),
        "sales": sales_rows,
        "assignments": await _count_assignments(session, tenant_id),
        "visits": visits_count,
        "travel_sheets": sheets_count,
        "problems": probleme_count,
    }


async def _count_assignments(session: AsyncSession, tenant_id: UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(AgentStoreAssignment)
        .where(AgentStoreAssignment.tenant_id == tenant_id)
    )
    return int(result.scalar_one() or 0)


async def wipe_tenant_data(session: AsyncSession, *, tenant_id: UUID) -> dict[str, int]:
    """
    Șterge TOATE datele tenantului (vânzări, canonical entities, aliases,
    batches, assignments). NU șterge userii, tenantul, audit log-urile sau
    api key-urile. Folosit ca reset rapid după demo.
    """
    from sqlalchemy import delete

    from app.modules.activitate.models import AgentVisit
    from app.modules.agents.models import Agent, AgentAlias, AgentStoreAssignment
    from app.modules.brands.models import Brand, BrandAlias
    from app.modules.parcurs.models import TravelSheet
    from app.modules.probleme.models import ActivityProblem
    from app.modules.product_categories.models import ProductCategoryAlias
    from app.modules.products.models import Product, ProductAlias
    from app.modules.sales.models import ImportBatch, RawSale
    from app.modules.stores.models import Store, StoreAlias

    counts: dict[str, int] = {}
    # ProductCategory e global — NU se șterge la wipe.
    # travel_sheet_entries + travel_sheet_fuel_fills se șterg cascade via FK.
    for model, key in [
        (AgentVisit, "visits"),
        (TravelSheet, "travel_sheets"),
        (ActivityProblem, "problems"),
        (RawSale, "sales"),
        (ImportBatch, "batches"),
        (AgentStoreAssignment, "assignments"),
        (StoreAlias, "store_aliases"),
        (AgentAlias, "agent_aliases"),
        (ProductAlias, "product_aliases"),
        (ProductCategoryAlias, "category_aliases"),
        (BrandAlias, "brand_aliases"),
        (Store, "stores"),
        (Agent, "agents"),
        (Product, "products"),
        (Brand, "brands"),
    ]:
        res = await session.execute(
            delete(model).where(model.tenant_id == tenant_id)
        )
        counts[key] = res.rowcount or 0

    await session.commit()
    return counts
