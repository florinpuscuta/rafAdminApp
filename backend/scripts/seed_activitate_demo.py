"""
Seed one-off pentru activitate + parcurs + probleme în tenantul Adpsika.

Rulare:
    docker exec adeplast-saas-backend-1 python scripts/seed_activitate_demo.py [TENANT_UUID]

Idempotent: dacă există deja rânduri în agent_visits pentru tenant, abandonează.
"""
import asyncio
import calendar
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.core.db import SessionLocal
# Force-import ALL module models ca SQLAlchemy să rezolve FK-urile cross-module.
from app.modules.tenants.models import Tenant  # noqa: F401
from app.modules.users.models import User  # noqa: F401
from app.modules.activitate.models import AgentVisit
from app.modules.agents.models import Agent
from app.modules.parcurs.models import (
    TravelSheet,
    TravelSheetEntry,
    TravelSheetFuelFill,
)
from app.modules.probleme.models import ActivityProblem
from app.modules.stores.models import Store


DEFAULT_TENANT = UUID("e6cd4519-a2b7-448c-b488-3597a70d3bc3")  # Adpsika


async def main(tenant_id: UUID) -> None:
    rng = random.Random(42)
    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(func.count())
                .select_from(AgentVisit)
                .where(AgentVisit.tenant_id == tenant_id)
            )
        ).scalar_one()
        if existing:
            print(f"agent_visits already has {existing} rows for tenant {tenant_id}; skipping seed.")
            return

        agents = (
            await session.execute(
                select(Agent).where(Agent.tenant_id == tenant_id).limit(10)
            )
        ).scalars().all()
        stores = (
            await session.execute(
                select(Store).where(Store.tenant_id == tenant_id).limit(80)
            )
        ).scalars().all()
        if not agents or not stores:
            print(f"no agents ({len(agents)}) or stores ({len(stores)}) for tenant {tenant_id}; abort")
            return

        today = date.today()
        visits = 0
        for _ in range(80):
            day = today - timedelta(days=rng.randint(0, 60))
            if day.weekday() >= 5:
                continue
            a = rng.choice(agents)
            s = rng.choice(stores)
            ci_h = rng.randint(8, 15)
            ci_m = rng.choice([0, 15, 30, 45])
            dur = rng.randint(25, 90)
            co_tot = ci_h * 60 + ci_m + dur
            co_h, co_m = divmod(co_tot, 60)
            session.add(AgentVisit(
                tenant_id=tenant_id, scope="adp",
                visit_date=day, agent_id=a.id, store_id=s.id,
                client=(s.name or "").upper(),
                check_in=f"{ci_h:02d}:{ci_m:02d}",
                check_out=f"{co_h:02d}:{co_m:02d}",
                duration_min=dur,
                km=Decimal(str(rng.randint(15, 120))),
                notes=rng.choice(
                    [None, None, "Verificare stoc", "Negociere contract", "Follow-up reclamatie"]
                ),
            ))
            visits += 1

        # Probleme
        now = date.today()
        samples = [
            "Intarzieri livrari zona Moldova.\nReclamatii calitate ciment vrac.",
            "Stoc limitat adezivi umezi in Oradea.\nConcurenta agresiva Baumit pe KA.",
            "Transport blocat — probleme administrative.",
        ]
        problems = 0
        for offset, text in enumerate(samples):
            m = now.month - offset
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            session.add(ActivityProblem(
                tenant_id=tenant_id, scope="adp",
                year=y, month=m, content=text,
                updated_by="seed@adeplast-saas.local",
            ))
            problems += 1
        session.add(ActivityProblem(
            tenant_id=tenant_id, scope="sika",
            year=now.year, month=now.month,
            content="SIKA: intarzieri livrari primer + reclamatii ambalare.",
            updated_by="seed@adeplast-saas.local",
        ))
        problems += 1

        # Parcurs — foaie pentru primul agent, luna curentă
        a = agents[0]
        days_in = calendar.monthrange(now.year, now.month)[1]
        wd = [
            date(now.year, now.month, d)
            for d in range(1, days_in + 1)
            if date(now.year, now.month, d).weekday() < 5
        ]
        num_days = len(wd) or 1
        total_km = 2400
        sheet = TravelSheet(
            tenant_id=tenant_id, scope="adp",
            agent_id=a.id, agent_name=a.full_name,
            year=now.year, month=now.month,
            car_number="BH 12 DEM", sediu="Oradea",
            km_start=50000, km_end=50000 + total_km,
            total_km=total_km, working_days=num_days,
            avg_km_per_day=Decimal(total_km) / Decimal(num_days),
            total_fuel_liters=Decimal("180"), total_fuel_cost=Decimal("1200"),
            ai_generated=False,
        )
        session.add(sheet)
        await session.flush()
        per_day = total_km // num_days
        cur = 50000
        day_names = ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]
        for d in wd:
            session.add(TravelSheetEntry(
                sheet_id=sheet.id, entry_date=d, day_name=day_names[d.weekday()],
                route="Oradea -> Teren -> Oradea",
                km_start=cur, km_end=cur + per_day, km_driven=per_day,
                purpose="Vizita comerciala",
            ))
            cur += per_day
        session.add(TravelSheetFuelFill(
            sheet_id=sheet.id,
            fill_date=wd[0] if wd else date(now.year, now.month, 1),
            liters=Decimal("90"), cost=Decimal("600"),
        ))

        await session.commit()
        print(f"OK tenant={tenant_id} visits={visits} problems={problems} sheets=1")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_TENANT)
    asyncio.run(main(UUID(arg)))
