"""Endpoint-uri pentru raport lunar complet.

- GET /api/monthly-report/full        → docx binary (blocant)
- GET /api/monthly-report/full/stream  → NDJSON streaming cu progres + docx base64 final
"""
from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_user
from app.modules.monthly_report import browser as browser_mod
from app.modules.monthly_report import builder, narrator, service
from app.modules.users.models import User

router = APIRouter(prefix="/api/monthly-report", tags=["monthly-report"])

# ─── Checklist de capitole (afișat live în UI) ────────────────────────────
CHAPTERS: list[tuple[str, str]] = [
    ("data_total",         "Colectare date — Total KA, YoY, YTD"),
    ("data_adeplast",      "Colectare date — Adeplast KA (brand + clienți + categorii + top 15 produse)"),
    ("data_sika",          "Colectare date — Sika KA (brand + clienți + categorii + top 15 produse)"),
    ("data_marca_privata", "Colectare date — Marcă Privată"),
    ("data_consolidated",  "Colectare date — Top clienți consolidați"),
    ("data_zones",         "Colectare date — Vânzări pe zone geografice"),
    ("data_evolution",     "Colectare date — Evoluție lunară YTD"),
    ("data_prices",        "Colectare date — Prețuri Adeplast + Sika × toate lanțurile"),
    ("data_marketing",     "Descărcare poze marketing (catalog/panouri/magazine)"),
    ("ai_exec_summary",    "Narațiune AI — Sumar executiv"),
    ("ai_adeplast",        "Narațiune AI — Analiza Adeplast KA"),
    ("ai_sika",            "Narațiune AI — Analiza Sika KA"),
    ("ai_consolidated",    "Narațiune AI — Analiza consolidată"),
    ("ai_conclusions",     "Narațiune AI — Concluzii și recomandări strategice"),
    ("ai_zones",           "Narațiune AI — Vânzări pe zone"),
    ("ai_prices",          "Narațiune AI — Analiza prețuri"),
    ("ai_marketing",       "Narațiune AI — Activități marketing"),
    ("screenshots",        "Capturi live din aplicație (toate paginile — Dashboard, Analize, Prețuri, Top Produse, Marketing)"),
    ("assemble",           "Asamblare document Word (chart-uri + tabele + poze + screenshots)"),
    ("done",               "Raport gata"),
]


def _brand_json(bd: service.BrandDossier) -> dict:
    def _yoy(y: service.YoY) -> dict:
        return {"current": round(y.current, 2), "prev": round(y.prev, 2),
                "diff": round(y.diff, 2),
                "pct": round(y.pct, 1) if y.pct is not None else None}
    def _rows(rs: list[service.Row]) -> list[dict]:
        return [
            {"label": r.label, "cur": round(r.cur, 2), "prev": round(r.prev, 2),
             "diff": round(r.diff, 2),
             "pct": round(r.pct, 1) if r.pct is not None else None}
            for r in rs
        ]
    return {
        "brand": bd.brand, "year": bd.year, "month": bd.month, "prev_year": bd.prev_year,
        "amount": _yoy(bd.amount), "quantity": _yoy(bd.quantity),
        "amount_ytd": _yoy(bd.amount_ytd), "quantity_ytd": _yoy(bd.quantity_ytd),
        "top_clients": _rows(bd.top_clients),
        "top_categories": _rows(bd.top_categories),
        "top_products": [
            {"code": pr.code, "name": pr.name, "category": pr.category,
             "cur": round(pr.cur, 2), "prev": round(pr.prev, 2),
             "pct": round(pr.pct, 1) if pr.pct is not None else None}
            for pr in bd.top_products
        ],
    }


def _full_json(d: service.FullDossier) -> dict:
    def _yoy(y: service.YoY) -> dict:
        return {"current": round(y.current, 2), "prev": round(y.prev, 2),
                "diff": round(y.diff, 2),
                "pct": round(y.pct, 1) if y.pct is not None else None}
    return {
        "year": d.year, "month": d.month, "prev_year": d.prev_year,
        "total": _yoy(d.total), "total_ytd": _yoy(d.total_ytd),
        "adeplast": _brand_json(d.adeplast),
        "sika": _brand_json(d.sika),
        "marca_privata": {
            "adeplast": _yoy(d.marca_privata.adeplast),
            "marca_privata": _yoy(d.marca_privata.marca_privata),
            "categories_pl": [
                {"label": c.label, "cur": round(c.cur, 2), "prev": round(c.prev, 2),
                 "pct": round(c.pct, 1) if c.pct is not None else None}
                for c in d.marca_privata.categories_pl
            ],
        },
        "consolidated_top_clients": [
            {"label": r.label, "cur": round(r.cur, 2), "prev": round(r.prev, 2),
             "pct": round(r.pct, 1) if r.pct is not None else None}
            for r in d.consolidated_top_clients
        ],
        "zones_top10": [
            {"zone": z.zone, "cur": round(z.amount_current, 2),
             "prev": round(z.amount_prev, 2),
             "pct": round(z.pct, 1) if z.pct is not None else None}
            for z in d.zones.zones[:10]
        ],
        "zones_total": {
            "current": round(d.zones.total_current, 2),
            "prev": round(d.zones.total_prev, 2),
            "pct": round(d.zones.total_pct, 1) if d.zones.total_pct is not None else None,
        },
        "monthly_evolution": [
            {"month": m, "current": round(c, 2), "prev": round(p, 2)}
            for m, c, p in d.monthly_evolution
        ],
        "prices": {
            "avg_advantage_pct": (
                round(d.prices.avg_advantage_pct, 1)
                if d.prices.avg_advantage_pct is not None else None
            ),
            "stores_covered": d.prices.stores_covered,
            "sample_rows": [
                {
                    "store": r.store, "group": r.group,
                    "product_adp": r.product_adp,
                    "price_adp": r.price_adp,
                    "avg_competitor": r.avg_competitor,
                    "advantage_pct": r.advantage_pct,
                }
                for r in d.prices.rows[:10]
            ],
        },
        "marketing": {
            "panouri_count": d.marketing.panouri_count,
            "magazine_count": d.marketing.magazine_count,
            "catalog_count": d.marketing.catalog_count,
            "catalog_folder": d.marketing.catalog_folder_name,
            "has_catalog_photos": len(d.marketing.catalog_photos) > 0,
            "has_panouri_photos": len(d.marketing.panouri_photos) > 0,
            "has_magazine_photos": len(d.marketing.magazine_photos) > 0,
        },
    }


async def _generate_full(
    session: AsyncSession, tenant_id, year: int, month: int,
    *, emit: callable | None = None,
    access_token: str | None = None,
    with_screenshots: bool = True,
) -> bytes:
    """Rulează pipeline-ul complet. `emit` primește evenimente de progres."""
    async def step(sid: str) -> None:
        if emit is not None:
            await emit({"kind": "step", "id": sid, "status": "done"})

    # Queries secvențiale (fiecare emite evenimentul după completare)
    d = await service.full_dossier(session, tenant_id, year=year, month=month)
    # Marcăm toate data_* deodată — queries rulate împreună
    for sid in ("data_total", "data_adeplast", "data_sika", "data_marca_privata",
                "data_consolidated", "data_zones", "data_evolution",
                "data_prices", "data_marketing"):
        await step(sid)

    full_json = _full_json(d)
    adp_json = _brand_json(d.adeplast)
    sika_json = _brand_json(d.sika)
    mp_json = full_json["marca_privata"] | {
        "year": d.year, "month": d.month, "prev_year": d.prev_year,
    }

    # AI narațiuni — paralel; emitem după fiecare await
    async def call_with_step(coro, sid: str) -> str:
        t = await coro
        await step(sid)
        return t

    (
        exec_text, adp_brand, adp_clients, adp_cats, mp_text,
        sika_brand, sika_clients, sika_cats, cons_text, concl_text,
        zones_text, price_text, mkt_text,
    ) = await asyncio.gather(
        call_with_step(narrator.narrate_executive_summary(tenant_id, {
            "year": d.year, "month": d.month, "prev_year": d.prev_year,
            "total": full_json["total"], "total_ytd": full_json["total_ytd"],
            "adeplast_summary": adp_json["amount"],
            "sika_summary": sika_json["amount"],
        }), "ai_exec_summary"),
        narrator.narrate_brand_section(tenant_id, "Adeplast", adp_json),
        narrator.narrate_clients_section(tenant_id, "Adeplast",
            {"year": d.year, "month": d.month, "top_clients": adp_json["top_clients"]}),
        narrator.narrate_categories_section(tenant_id, "Adeplast",
            {"year": d.year, "month": d.month, "top_categories": adp_json["top_categories"]}),
        narrator.narrate_marca_privata(tenant_id, mp_json),
        narrator.narrate_brand_section(tenant_id, "Sika", sika_json),
        narrator.narrate_clients_section(tenant_id, "Sika",
            {"year": d.year, "month": d.month, "top_clients": sika_json["top_clients"]}),
        narrator.narrate_categories_section(tenant_id, "Sika",
            {"year": d.year, "month": d.month, "top_categories": sika_json["top_categories"]}),
        call_with_step(narrator.narrate_consolidated(tenant_id, {
            "year": d.year, "month": d.month,
            "total": full_json["total"],
            "top_clients": full_json["consolidated_top_clients"][:8],
        }), "ai_consolidated"),
        call_with_step(narrator.narrate_conclusions(tenant_id, full_json), "ai_conclusions"),
        call_with_step(narrator.narrate_zones(tenant_id, {
            "year": d.year, "month": d.month, "prev_year": d.prev_year,
            "total": full_json["zones_total"],
            "zones_top10": full_json["zones_top10"],
        }), "ai_zones"),
        call_with_step(narrator.narrate_prices(tenant_id, full_json["prices"]), "ai_prices"),
        call_with_step(narrator.narrate_marketing(tenant_id, full_json["marketing"]), "ai_marketing"),
    )
    # Marcăm adeplast/sika când toate sub-secțiunile lor sunt gata
    await step("ai_adeplast")
    await step("ai_sika")

    narratives = {
        "exec_summary": exec_text,
        "adeplast_brand": adp_brand,
        "adeplast_clients": adp_clients,
        "adeplast_categories": adp_cats,
        "marca_privata": mp_text,
        "sika_brand": sika_brand,
        "sika_clients": sika_clients,
        "sika_categories": sika_cats,
        "consolidated": cons_text,
        "conclusions": concl_text,
        "zones": zones_text,
        "prices": price_text,
        "marketing": mkt_text,
    }
    # Capturi live din aplicație (opțional)
    shots = []
    if with_screenshots and access_token:
        try:
            shots = await browser_mod.capture_pages(access_token=access_token)
        except Exception:
            pass
    await step("screenshots")

    docx_bytes = builder.build_full_report_docx(
        d, narratives=narratives, app_screenshots=shots,
    )
    await step("assemble")
    await step("done")
    return docx_bytes


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


@router.get("/full")
async def full_report(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    screenshots: bool = Query(True),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Raport complet (blocant) — returnează docx binary."""
    token = _extract_token(request)
    docx_bytes = await _generate_full(
        session, current_user.tenant_id, year, month,
        access_token=token, with_screenshots=screenshots,
    )
    filename = f"raport-ka-management-{year}-{month:02d}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/full/stream")
async def full_report_stream(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    screenshots: bool = Query(True),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Streaming NDJSON:
      - Inițial: {"kind": "chapters", "items": [...]}
      - Progres: {"kind": "step", "id": "...", "status": "done"}
      - Final:   {"kind": "result", "filename": "...", "docx_b64": "..."}
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def emit(ev: dict[str, Any]) -> None:
        await queue.put(ev)

    async def runner() -> None:
        try:
            # Trimite întâi lista capitolelor
            await queue.put({
                "kind": "chapters",
                "items": [{"id": i, "label": l} for i, l in CHAPTERS],
            })
            token = _extract_token(request)
            docx_bytes = await _generate_full(
                session, current_user.tenant_id, year, month, emit=emit,
                access_token=token, with_screenshots=screenshots,
            )
            filename = f"raport-ka-management-{year}-{month:02d}.docx"
            await queue.put({
                "kind": "result",
                "filename": filename,
                "docx_b64": base64.b64encode(docx_bytes).decode("ascii"),
            })
        except Exception as e:
            await queue.put({"kind": "error", "message": str(e)})
        finally:
            await queue.put({"kind": "_end_"})

    task = asyncio.create_task(runner())

    async def stream() -> AsyncIterator[bytes]:
        try:
            while True:
                ev = await queue.get()
                if ev.get("kind") == "_end_":
                    break
                yield (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
        finally:
            task.cancel()

    return StreamingResponse(stream(), media_type="application/x-ndjson")


# ─── Screenshots-only report ───────────────────────────────────────────────

@router.get("/screenshots")
async def screenshots_report(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Raport doar cu screenshots — fără date, fără AI.

    Parcurge aplicația pagină cu pagină și construiește un docx cu toate
    capturile, una după alta, fiecare pe landscape A4.
    """
    token = _extract_token(request)
    if not token:
        return Response(content=b"Token missing", status_code=401)
    shots = await browser_mod.capture_pages(access_token=token)
    docx_bytes = builder.build_screenshots_only_docx(shots)
    filename = "capturi-aplicatie.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/screenshots/stream")
async def screenshots_report_stream(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Streaming NDJSON pentru raportul de screenshots.

    Evenimente:
      - {"kind":"chapters","items":[{"id":"capture_<n>","label":"<label>"}...]}
      - {"kind":"step","id":"capture_<n>","status":"done"}
      - {"kind":"result","filename":"...","docx_b64":"..."}
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()
    token = _extract_token(request)

    async def runner() -> None:
        try:
            if not token:
                await queue.put({"kind": "error", "message": "Token lipsă"})
                return
            chapters_items = [
                {"id": f"capture_{i}", "label": label}
                for i, (label, _p, _s) in enumerate(browser_mod.PAGES)
            ]
            await queue.put({"kind": "chapters", "items": chapters_items})

            async def on_progress(ev: dict) -> None:
                if ev.get("status") == "done":
                    await queue.put({
                        "kind": "step",
                        "id": f"capture_{ev.get('index')}",
                        "status": "done",
                    })

            shots = await browser_mod.capture_pages(
                access_token=token, on_progress=on_progress,
            )
            docx_bytes = builder.build_screenshots_only_docx(shots)
            await queue.put({
                "kind": "result",
                "filename": "capturi-aplicatie.docx",
                "docx_b64": base64.b64encode(docx_bytes).decode("ascii"),
            })
        except Exception as e:
            await queue.put({"kind": "error", "message": str(e)})
        finally:
            await queue.put({"kind": "_end_"})

    task = asyncio.create_task(runner())

    async def stream() -> AsyncIterator[bytes]:
        try:
            while True:
                ev = await queue.get()
                if ev.get("kind") == "_end_":
                    break
                yield (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
        finally:
            task.cancel()

    return StreamingResponse(stream(), media_type="application/x-ndjson")
