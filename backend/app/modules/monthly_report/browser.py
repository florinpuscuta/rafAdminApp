"""Headless browser screenshots — Playwright chromium.

Deschide aplicația propriu-zisă (krossdash.ro) cu JWT-ul userului injectat
în localStorage și face screenshot la fiecare pagină din lista configurată.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

log = logging.getLogger("adeplast.monthly_report.browser")

# URL-ul prin care browser-ul accesează aplicația. Trebuie prin Caddy ca să
# rutăm corect /api/* către backend. Folosim public URL (krossdash.ro) —
# containerul are ieșire la internet. Alternativ, putem hit caddy intern cu
# Host header corect.
FRONTEND_URL_DEFAULT = "https://krossdash.ro"


@dataclass
class PageShot:
    """Screenshot cu meta-date pentru captură."""
    label: str           # titlu capitol în raport
    path: str            # path relativ din app (ex: "/dashboard", "/analiza/luni")
    png_bytes: bytes
    width: int
    height: int


# Lista paginilor de capturat, în ordinea din raport.
# Păstrăm doar paginile cu tabele/graficuri relevante, evităm chat/taskuri.
PAGES: list[tuple[str, str, str]] = [
    # (label, path, company_scope)
    ("Vedere Generală — SIKADP", "/", "sikadp"),
    ("Analiza pe luni — SIKADP", "/analiza/luni", "sikadp"),
    ("Vz la zi — SIKADP", "/analiza/zi", "sikadp"),
    ("Consolidat — SIKADP", "/consolidat", "sikadp"),

    ("Adeplast — Consolidat", "/consolidat", "adeplast"),
    ("Adeplast — Analiza pe luni", "/analiza/luni", "adeplast"),
    ("Adeplast — Prețuri Comparative", "/prices/comparative", "adeplast"),
    ("Adeplast — Pret 3 Net Comp KA", "/prices/pret3net", "adeplast"),
    ("Adeplast — Propuneri Listare", "/prices/propuneri", "adeplast"),
    ("Adeplast — Cross-KA (prețuri proprii)", "/prices/own", "adeplast"),
    ("Adeplast — Arbore Grupe Produse", "/grupe-arbore", "adeplast"),
    ("Adeplast — Mortare Silozuri (Vrac)", "/mortar", "adeplast"),
    ("Adeplast — EPS Detalii", "/eps", "adeplast"),
    ("Adeplast — Marcă Privată", "/privatelabel", "adeplast"),
    ("Adeplast — Prețuri KA vs Retail", "/prices/ka-retail", "adeplast"),
    ("Adeplast — Prognoza Vânzări", "/forecast", "adeplast"),
    ("Adeplast — Top Mortare Uscate", "/topprod/mu", "adeplast"),
    ("Adeplast — Top EPS", "/topprod/eps", "adeplast"),
    ("Adeplast — Top Umede", "/topprod/umede", "adeplast"),
    ("Adeplast — Top Dibluri", "/topprod/dibluri", "adeplast"),
    ("Adeplast — Top Vărsaci", "/topprod/varsaci", "adeplast"),

    ("Sika — Consolidat", "/consolidat", "sika"),
    ("Sika — Analiza pe luni", "/analiza/luni", "sika"),
    ("Sika — Prețuri Comparative", "/prices/comparative", "sika"),
    ("Sika — Top Building Finishing", "/topprod/tm-bf", "sika"),
    ("Sika — Top Sealing & Bonding", "/topprod/tm-sb", "sika"),
    ("Sika — Top Waterproofing & Roofing", "/topprod/tm-wp", "sika"),
    ("Sika — Top Concrete & Anchors", "/topprod/tm-ca", "sika"),
    ("Sika — Top Flooring", "/topprod/tm-fl", "sika"),
    ("Sika — Top Industry & Accessories", "/topprod/tm-ia", "sika"),

    ("Marketing — Facing Tracker", "/marketing/facing", "sikadp"),
    ("Marketing — Panouri & Standuri", "/marketing/panouri", "sikadp"),
    ("Marketing — Acțiuni Concurență", "/marketing/concurenta", "sikadp"),
    ("Marketing — Catalog Lunar", "/marketing/catalog", "sikadp"),
    ("Marketing — Poze din Magazine", "/gallery", "sikadp"),
    ("Marketing — Acțiuni Sika", "/marketing/sika", "sikadp"),
]


async def capture_pages(
    *,
    access_token: str,
    frontend_url: str | None = None,
    pages: list[tuple[str, str, str]] | None = None,
    viewport_w: int = 1440,
    viewport_h: int = 900,
    on_progress: callable | None = None,
) -> list[PageShot]:
    """Captează screenshots pentru toate paginile configurate.

    Flow:
      1. Launch chromium headless
      2. Navigate la / → setează localStorage `adeplast_token` și scope-ul SIKADP/ADP/SIKA
      3. Pentru fiecare (label, path, scope):
         - Setează scope-ul în localStorage
         - Navigate la path
         - Wait for network idle + extra settle
         - Screenshot full-page
      4. Return list[PageShot]
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:  # pragma: no cover
        log.warning("Playwright not installed — returning empty screenshots")
        return []

    pages = pages or PAGES
    frontend_url = frontend_url or FRONTEND_URL_DEFAULT
    out: list[PageShot] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": viewport_w, "height": viewport_h},
            device_scale_factor=1.2,
            ignore_https_errors=True,
        )
        # addInitScript: rulează în fiecare context ÎNAINTE ca pagina să
        # execute JS-ul ei. Așa token-ul e deja în localStorage la primul render.
        await context.add_init_script(
            f"""
            (function() {{
                try {{
                    localStorage.setItem('adeplast_token', {access_token!r});
                    localStorage.setItem('adeplast_company_scope', 'sikadp');
                    // Dismiss cookie consent dacă e setat
                    localStorage.setItem('adeplast_cookie_consent', 'accepted');
                }} catch (e) {{}}
            }})();
            """
        )
        page = await context.new_page()

        # Ping inițial — verificăm că reach-ul funcționează
        try:
            resp = await page.goto(
                frontend_url + "/", wait_until="networkidle", timeout=25000,
            )
            if resp:
                log.info(f"initial nav status={resp.status}")
            await asyncio.sleep(2.0)
        except Exception:
            log.exception("initial navigation failed")
            await browser.close()
            return out

        # 4. Captează fiecare pagină
        for idx, (label, path, scope) in enumerate(pages):
            try:
                if on_progress:
                    await on_progress({
                        "index": idx, "total": len(pages),
                        "label": label, "status": "loading",
                    })

                # Setează scope-ul ÎNAINTE de goto
                await page.evaluate(
                    """(scope) => {
                        try { localStorage.setItem('adeplast_company_scope', scope); } catch (e) {}
                    }""",
                    scope,
                )
                await page.goto(
                    frontend_url + path,
                    wait_until="networkidle",
                    timeout=25000,
                )
                # Dacă pagina s-a redirecționat la /login → try to re-auth și retry
                cur_url = page.url
                if "/login" in cur_url:
                    log.warning(f"got redirected to /login for {path} — retrying")
                    await page.evaluate(
                        f"() => {{ localStorage.setItem('adeplast_token', {access_token!r}); }}"
                    )
                    await page.goto(
                        frontend_url + path,
                        wait_until="networkidle",
                        timeout=25000,
                    )
                # Așteaptă settle + chart animations (Chart.js are 750ms default)
                await asyncio.sleep(2.5)

                # Curățenie vizuală: ascunde FAB-uri + cookie banner
                await page.evaluate(
                    """() => {
                        document.querySelectorAll('[data-fab="true"]').forEach(e => e.style.display='none');
                        document.querySelectorAll('[data-cookie-consent]').forEach(e => e.style.display='none');
                    }"""
                )

                png = await page.screenshot(
                    full_page=True,
                    type="png",
                    animations="disabled",
                )
                # Mărimea efectivă
                box = await page.evaluate(
                    "() => ({ w: document.body.scrollWidth, h: document.body.scrollHeight })"
                )
                out.append(PageShot(
                    label=label, path=path, png_bytes=png,
                    width=int(box.get("w") or viewport_w),
                    height=int(box.get("h") or viewport_h),
                ))
                if on_progress:
                    await on_progress({
                        "index": idx, "total": len(pages),
                        "label": label, "status": "done",
                    })
            except Exception as e:
                log.exception(f"screenshot failed for {path}: {e}")
                if on_progress:
                    await on_progress({
                        "index": idx, "total": len(pages),
                        "label": label, "status": "failed",
                        "error": str(e),
                    })

        await browser.close()

    return out
