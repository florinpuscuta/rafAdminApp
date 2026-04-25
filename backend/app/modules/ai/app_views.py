"""
Dispatcher de "view-uri" la nivel de aplicație, expus ca tool AI.

Asistentul AI cheamă `get_app_view(view_name, params)` și primește EXACT
output-ul service-ului care alimentează pagina UI corespunzătoare. Așa
poate raporta numere identice cu cele din meniuri (ex. Marja Lunara
22.62% pentru Apr 2026), fără să replice logica complexă în SQL.

READ-ONLY. Niciun side-effect.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


_SCOPE_TO_SLUG = {"adp": "adeplast", "sika": "sika"}


async def _resolve_tenant_for_scope(
    session: AsyncSession,
    tenant_ids: list[UUID],
    scope: str | None,
) -> UUID:
    """În SIKADP user-ul are mai multe org_ids; pickăm pe cel cu slug
    matching pe scope. `scope='sikadp'` păstrează primul (service-urile
    *_for_sikadp se ocupă intern de merge)."""
    if not tenant_ids:
        raise ValueError("Niciun tenant autorizat.")
    if len(tenant_ids) == 1:
        return tenant_ids[0]
    if scope == "sikadp":
        return tenant_ids[0]
    target_slug = _SCOPE_TO_SLUG.get((scope or "").lower())
    if target_slug:
        from app.modules.tenants.models import Organization
        res = await session.execute(
            select(Organization.id).where(
                Organization.id.in_(tenant_ids),
                Organization.slug == target_slug,
            )
        )
        match = res.scalar_one_or_none()
        if match is not None:
            return match
    return tenant_ids[0]


def _to_jsonable(obj: Any) -> Any:
    """Conversie best-effort la dict JSON-serializable."""
    from decimal import Decimal
    from datetime import datetime
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        try:
            return _to_jsonable(obj.model_dump(mode="json"))
        except Exception:
            return _to_jsonable(obj.model_dump())
    if is_dataclass(obj):
        return _to_jsonable(asdict(obj))
    if hasattr(obj, "__dict__"):
        return _to_jsonable({
            k: v for k, v in vars(obj).items() if not k.startswith("_")
        })
    return str(obj)


# ── Handlers ──────────────────────────────────────────────────────────────


async def _h_marja_lunara(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.marja_lunara.service import build_marja_lunara
    scope = (p.get("scope") or "adp").lower()
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    return await build_marja_lunara(
        session, tenant_id=tid, scope=scope,
        from_year=int(p["from_year"]), from_month=int(p["from_month"]),
        to_year=int(p["to_year"]), to_month=int(p["to_month"]),
    )


async def _h_margine(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.margine.service import build_margine
    scope = (p.get("scope") or "adp").lower()
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    return await build_margine(
        session, tenant_id=tid, scope=scope,
        from_year=int(p["from_year"]), from_month=int(p["from_month"]),
        to_year=int(p["to_year"]), to_month=int(p["to_month"]),
    )


async def _h_analiza_pe_luni(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.analizapeluni import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p["year_curr"])
    if scope == "sikadp":
        tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
        return await svc.get_for_sikadp(session, tid, year_curr=year)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    fn = svc.get_for_adp if scope == "adp" else svc.get_for_sika
    return await fn(session, tid, year_curr=year)


async def _h_vz_la_zi(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.vz_la_zi import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p["year_curr"])
    month = int(p["month"])
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    if scope == "sikadp":
        return await svc.get_for_sikadp(session, tid, year_curr=year, month=month)
    fn = svc.get_for_adp if scope == "adp" else svc.get_for_sika
    return await fn(session, tid, year_curr=year, month=month)


async def _h_top_produse(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.top_produse import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p["year_curr"])
    cat_id = p.get("category_id")
    if cat_id is not None and not isinstance(cat_id, UUID):
        cat_id = UUID(str(cat_id))
    limit = int(p.get("limit", 20))
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    if scope == "sikadp":
        return await svc.get_for_sikadp(
            session, tid, year_curr=year, category_id=cat_id, limit=limit,
        )
    fn = svc.get_for_adp if scope == "adp" else svc.get_for_sika
    return await fn(session, tid, year_curr=year, category_id=cat_id, limit=limit)


async def _h_consolidat_ka(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.consolidat import service as svc
    company = (p.get("company") or "adeplast").lower()
    y2 = int(p.get("y2") or date.today().year)
    y1 = int(p.get("y1") or (y2 - 1))
    months = p.get("months") or list(range(1, date.today().month + 1))
    if not isinstance(months, list):
        months = [int(months)]
    tid = await _resolve_tenant_for_scope(
        session, tenant_ids,
        "sikadp" if company == "sikadp" else
        ("adp" if company == "adeplast" else "sika"),
    )
    totals = await svc.totals_for_company(
        session, tid, company=company, y1=y1, y2=y2, months=months,
    )
    by_agent = await svc.by_agent(
        session, tid, company=company, y1=y1, y2=y2, months=months,
    )
    return {"totals": totals, "by_agent": by_agent}


async def _h_targhet(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.targhet import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p.get("year_curr") or date.today().year)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    if scope == "sikadp":
        return await svc.get_for_sikadp_merged(session, tid, year_curr=year)
    fn = svc.get_for_adp if scope == "adp" else svc.get_for_sika
    return await fn(session, tid, year_curr=year)


async def _h_evaluare_dashboard(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.evaluare_agenti import service as svc
    year = int(p.get("year") or date.today().year)
    months = p.get("months")
    if months is not None and not isinstance(months, list):
        months = [int(months)]
    return await svc.build_dashboard_merged(
        session, list(tenant_ids), year=year, months=months,
    )


async def _h_evaluare_agent_annual(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.evaluare_agenti import service as svc
    aid = p["agent_id"]
    if not isinstance(aid, UUID):
        aid = UUID(str(aid))
    year = int(p.get("year") or date.today().year)
    return await svc.build_agent_annual_breakdown_merged(
        session, list(tenant_ids), agent_id=aid, year=year,
    )


async def _h_prognoza(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.prognoza import service as svc
    scope = (p.get("scope") or "adp").lower()
    horizon = int(p.get("horizon_months") or 3)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    return await svc.get_forecast(
        session, tid, scope=scope, horizon_months=horizon,
    )


async def _h_rapoarte_lunar(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.rapoarte_lunar import service as svc
    today = date.today()
    year = int(p.get("year") or today.year)
    month = int(p.get("month") or today.month)
    tid = tenant_ids[0]
    return await svc.build_raport(session, tid, year=year, month=month)


async def _h_bonusari(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.bonusari import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p.get("year_curr") or date.today().year)
    month = p.get("month")
    if month is not None:
        month = int(month)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    if scope == "sikadp":
        return await svc.get_for_sikadp(
            session, tid, year_curr=year, month=month,
        )
    fn = svc.get_for_adp if scope == "adp" else svc.get_for_sika
    return await fn(session, tid, year_curr=year, month=month)


async def _h_grupe_tree(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.grupe_produse import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p.get("year") or date.today().year)
    months = p.get("months")
    if months is not None and not isinstance(months, list):
        months = [int(months)]
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    return await svc.build_tree(
        session, tid, scope=scope, year=year, months=months,
    )


async def _h_grupe_tree_by_client(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.grupe_produse import service as svc
    scope = (p.get("scope") or "adp").lower()
    year = int(p.get("year") or date.today().year)
    months = p.get("months")
    if months is not None and not isinstance(months, list):
        months = [int(months)]
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    return await svc.build_tree_by_client(
        session, tid, scope=scope, year=year, months=months,
    )


async def _h_eps_details(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.eps import service as svc
    today = date.today()
    y2 = int(p.get("y2") or today.year)
    y1 = int(p.get("y1") or (y2 - 1))
    months = p.get("months")
    if months is not None and not isinstance(months, list):
        months = [int(months)]
    tid = tenant_ids[0]
    return await svc.details_by_month(session, tid, y1=y1, y2=y2, months=months)


async def _h_mortare(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.mortare import service as svc
    year = int(p.get("year_curr") or date.today().year)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, "adp")
    return await svc.get_for_adp(session, tid, year_curr=year)


async def _h_marca_privata(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.marca_privata import service as svc
    year = int(p.get("year_curr") or date.today().year)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, "adp")
    return await svc.get_for_adp(session, tid, year_curr=year)


async def _h_comenzi_fara_ind(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.comenzi_fara_ind import service as svc
    scope = (p.get("scope") or "adp").lower()
    rd = p.get("report_date")
    if rd and isinstance(rd, str):
        rd = date.fromisoformat(rd)
    tid = await _resolve_tenant_for_scope(session, tenant_ids, scope)
    fn = svc.get_for_adp if scope == "adp" else svc.get_for_sika
    return await fn(session, tid, report_date=rd)


async def _h_promo_simulate(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.promotions.service import simulate
    pid = p["promo_id"]
    if not isinstance(pid, UUID):
        pid = UUID(str(pid))
    baseline = p.get("baseline_kind", "yoy")
    overrides = p.get("manual_quantities_override")
    data = None
    for tid in tenant_ids:
        data = await simulate(
            session, tenant_id=tid, promo_id=pid,
            baseline_kind=baseline, manual_quantities_override=overrides,
        )
        if data is not None:
            break
    return data


async def _h_monthly_report(
    session: AsyncSession, tenant_ids: list[UUID], p: dict,
) -> Any:
    from app.modules.monthly_report import service as svc
    today = date.today()
    year = int(p.get("year") or today.year)
    month = int(p.get("month") or today.month)
    tid = tenant_ids[0]
    return await svc.full_dossier(session, tid, year=year, month=month)


# ── Registry ──────────────────────────────────────────────────────────────


_VIEWS: dict[str, dict] = {
    "marja_lunara": {
        "fn": _h_marja_lunara,
        "doc": "Marjă netă lunară pe scope KA, agregată pe categorii/TM cu alocare discounturi unmapped (= numerele din meniul Marja Lunara).",
        "params_doc": "scope (adp|sika|sikadp), from_year, from_month, to_year, to_month",
    },
    "margine": {
        "fn": _h_margine,
        "doc": "Marjă brută/netă pe interval, defalcată pe grupe + lista produselor fără cost mapat.",
        "params_doc": "scope, from_year, from_month, to_year, to_month",
    },
    "analiza_pe_luni": {
        "fn": _h_analiza_pe_luni,
        "doc": "Vânzări per agent × 12 luni Y vs Y-1.",
        "params_doc": "scope, year_curr",
    },
    "vz_la_zi": {
        "fn": _h_vz_la_zi,
        "doc": "Vânzări la zi: prev/curr sales, nelivrate, nefacturate, exercițiu, gap YoY pentru o lună.",
        "params_doc": "scope, year_curr, month",
    },
    "top_produse": {
        "fn": _h_top_produse,
        "doc": "Top N produse într-o categorie, Y vs Y-1, defalcat lunar.",
        "params_doc": "scope, year_curr, category_id, limit (default 20)",
    },
    "consolidat_ka": {
        "fn": _h_consolidat_ka,
        "doc": "Vânzări KA consolidate: totals + by_agent.",
        "params_doc": "company (adeplast|sika|sikadp), y1, y2, months (list[int])",
    },
    "targhet": {
        "fn": _h_targhet,
        "doc": "Targhet × 12 luni per agent: prev/curr/target/gap/achievement_pct.",
        "params_doc": "scope, year_curr",
    },
    "evaluare_dashboard": {
        "fn": _h_evaluare_dashboard,
        "doc": "Dashboard agenți: vânzări, cheltuieli, bonus, cost_pct.",
        "params_doc": "year, months (list[int]|None)",
    },
    "evaluare_agent_annual": {
        "fn": _h_evaluare_agent_annual,
        "doc": "Defalcare anuală un agent (12 luni × salariu/bonus/cheltuieli).",
        "params_doc": "agent_id, year",
    },
    "prognoza": {
        "fn": _h_prognoza,
        "doc": "Forecast vânzări pe orizont N luni (history + forecast + per agent).",
        "params_doc": "scope, horizon_months (default 3)",
    },
    "rapoarte_lunar": {
        "fn": _h_rapoarte_lunar,
        "doc": "Raport lunar: KPI YoY + top clienți + top agenți + chain breakdown.",
        "params_doc": "year, month",
    },
    "bonusari": {
        "fn": _h_bonusari,
        "doc": "Calcul bonus per agent × 12 luni (growth_pct, bonus, recovery, total).",
        "params_doc": "scope, year_curr, month (opt)",
    },
    "grupe_tree": {
        "fn": _h_grupe_tree,
        "doc": "Arbore Brand → Categorie → Produs sortat DESC.",
        "params_doc": "scope, year, months (list[int]|None)",
    },
    "grupe_tree_by_client": {
        "fn": _h_grupe_tree_by_client,
        "doc": "Arbore Client KA → Categorie → Produs.",
        "params_doc": "scope, year, months (list[int]|None)",
    },
    "eps_details": {
        "fn": _h_eps_details,
        "doc": "EPS detalii per lună: Y1 vs Y2 cu diff/pct.",
        "params_doc": "y1, y2, months (list[int]|None)",
    },
    "mortare": {
        "fn": _h_mortare,
        "doc": "Mortare silozuri Adeplast: 12 luni + lista produselor.",
        "params_doc": "year_curr",
    },
    "marca_privata": {
        "fn": _h_marca_privata,
        "doc": "Marca privată per lanț × categorii (MU/EPS/UMEDE), 12 luni Y vs Y-1.",
        "params_doc": "year_curr",
    },
    "comenzi_fara_ind": {
        "fn": _h_comenzi_fara_ind,
        "doc": "Comenzi fără indicativ la o data snapshot dată.",
        "params_doc": "scope (adp|sika), report_date (ISO opt)",
    },
    "promotion_simulate": {
        "fn": _h_promo_simulate,
        "doc": "Simulare promoție: baseline vs scenario (rev/cost/profit/margin) + monthly + per-product.",
        "params_doc": "promo_id, baseline_kind (yoy|mom), manual_quantities_override (opt)",
    },
    "monthly_report_full": {
        "fn": _h_monthly_report,
        "doc": "Dossier complet pentru raportul lunar Word (input AI narator).",
        "params_doc": "year, month",
    },
}


VIEW_NAMES = sorted(_VIEWS.keys())


def list_view_descriptions() -> str:
    """Pentru system prompt: bullet-list cu nume, descriere și params."""
    lines = []
    for name in VIEW_NAMES:
        e = _VIEWS[name]
        lines.append(f"  - `{name}`: {e['doc']} Params: {e['params_doc']}")
    return "\n".join(lines)


async def get_app_view(
    session: AsyncSession,
    tenant_ids: list[UUID],
    view_name: str,
    params: dict | None = None,
) -> dict:
    """Dispatcher: caută view-ul, apelează handler-ul, serializează."""
    entry = _VIEWS.get((view_name or "").strip())
    if entry is None:
        return {
            "error": f"View necunoscut: '{view_name}'.",
            "available": VIEW_NAMES,
        }
    try:
        result = await entry["fn"](session, tenant_ids, params or {})
        return {
            "view": view_name,
            "data": _to_jsonable(result),
        }
    except KeyError as exc:
        return {"error": f"Param obligatoriu lipsă: {exc}"}
    except (TypeError, ValueError) as exc:
        return {"error": f"Param invalid: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Eroare în view '{view_name}': {exc}"}
