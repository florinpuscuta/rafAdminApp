"""
Module registry — un singur loc în care se înregistrează modulele.
Fiecare modul expune doar un `router` (APIRouter). Adăugarea/eliminarea
unui modul = adăugarea/eliminarea unei linii aici.
"""
from fastapi import APIRouter

from app.modules.activitate.router import router as activitate_router
from app.modules.agents.router import router as agents_router
from app.modules.ai.router import router as ai_router
from app.modules.analiza_magazin.router import router as analiza_magazin_router
from app.modules.analiza_pe_luni.router import router as analiza_pe_luni_router
from app.modules.app_settings.router import router as app_settings_router
from app.modules.api_keys.router import router as api_keys_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.bonusari.router import router as bonusari_router
from app.modules.brands.router import router as brands_router
from app.modules.comenzi_fara_ind.router import router as comenzi_fara_ind_router
from app.modules.consolidat.router import router as consolidat_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.demo.router import router as demo_router
from app.modules.eps.router import router as eps_router
from app.modules.evaluare_agenti.router import router as evaluare_agenti_router
from app.modules.gallery.router import router as gallery_router
from app.modules.grupe_produse.router import router as grupe_produse_router
from app.modules.mappings.router import router as mappings_router
from app.modules.marca_privata.router import router as marca_privata_router
from app.modules.mkt_catalog.router import router as mkt_catalog_router
from app.modules.mkt_concurenta.router import router as mkt_concurenta_router
from app.modules.mkt_facing.router import router as mkt_facing_router
from app.modules.mkt_panouri.router import router as mkt_panouri_router
from app.modules.mkt_sika.router import router as mkt_sika_router
from app.modules.monthly_report.router import router as monthly_report_router
from app.modules.mortare.router import router as mortare_router
from app.modules.orders.router import router as orders_router
from app.modules.parcurs.router import router as parcurs_router
from app.modules.prices.router import router as prices_router
from app.modules.probleme.router import router as probleme_router
from app.modules.product_categories.router import router as product_categories_router
from app.modules.products.router import router as products_router
from app.modules.prognoza.router import router as prognoza_router
from app.modules.rapoarte_lunar.router import router as rapoarte_lunar_router
from app.modules.rapoarte_word.router import router as rapoarte_word_router
from app.modules.reports.router import router as reports_router
from app.modules.sales.router import router as sales_router
from app.modules.stores.router import router as stores_router
from app.modules.targhet.router import router as targhet_router
from app.modules.taskuri.router import router as taskuri_router
from app.modules.tenants.router import router as tenants_router
from app.modules.top_produse.router import router as top_produse_router
from app.modules.users.router import router as users_router
from app.modules.vz_la_zi.router import router as vz_la_zi_router

MODULE_ROUTERS: list[APIRouter] = [
    auth_router,
    tenants_router,
    users_router,
    stores_router,
    agents_router,
    products_router,
    sales_router,
    orders_router,
    dashboard_router,
    audit_router,
    api_keys_router,
    gallery_router,
    reports_router,
    ai_router,
    demo_router,
    prices_router,
    product_categories_router,
    brands_router,
    eps_router,
    consolidat_router,
    mappings_router,
    vz_la_zi_router,
    analiza_pe_luni_router,
    analiza_magazin_router,
    comenzi_fara_ind_router,
    # Feature migrations
    grupe_produse_router,
    top_produse_router,
    marca_privata_router,
    mortare_router,
    targhet_router,
    bonusari_router,
    prognoza_router,
    activitate_router,
    parcurs_router,
    probleme_router,
    mkt_concurenta_router,
    mkt_catalog_router,
    mkt_facing_router,
    mkt_panouri_router,
    mkt_sika_router,
    rapoarte_word_router,
    rapoarte_lunar_router,
    monthly_report_router,
    taskuri_router,
    app_settings_router,
    evaluare_agenti_router,
]
