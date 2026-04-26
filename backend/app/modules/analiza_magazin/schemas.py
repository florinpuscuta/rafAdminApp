from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class AMStoreOption(APISchema):
    """Un magazin cu vânzări în fereastra de analiză."""
    key: str            # valoarea RawSale.client (folosită ca identificator)
    label: str          # afișat în UI (momentan identic cu key)
    chain: str          # "Dedeman" | "Altex" | "Leroy Merlin" | "Hornbach"
    agent: str | None = None  # agent dominant (cel cu cele mai multe rânduri)


class AMStoresResponse(APISchema):
    scope: str          # "adp" | "sika"
    months_window: int  # 3
    stores: list[AMStoreOption] = Field(default_factory=list)


class AMGapProduct(APISchema):
    product_id: UUID
    product_code: str
    product_name: str
    category: str | None      # "MU"|"EPS"|"UMEDE"|... (adp) sau TM label (sika)
    chain_qty: Decimal
    chain_value: Decimal
    stores_selling_count: int


class AMCategoryBreakdown(APISchema):
    """Contorul per categorie / TM pentru filtrarea dinamică în UI."""
    category: str | None      # None = „fără categorie"
    chain_sku_count: int
    own_sku_count: int
    gap_count: int


class AMResponse(APISchema):
    scope: str                # "adp" | "sika"
    store: str                # cheia magazinului selectat (RawSale.client)
    chain: str                # "Dedeman"/"Altex"/"Leroy Merlin"/"Hornbach"
    months_window: int        # 3
    chain_sku_count: int
    own_sku_count: int
    gap_count: int
    gap: list[AMGapProduct] = Field(default_factory=list)
    breakdown: list[AMCategoryBreakdown] = Field(default_factory=list)


# ── Insights (rank + must-list) ──────────────────────────────────────────


class AMRank(APISchema):
    """Poziția magazinului în clasament + total."""
    rank: int                # 1 = primul
    total: int               # total magazine clasate
    pct_top: float           # 100 * (1 - rank/total) — cu cât mai mare, mai bun


class AMMustListProduct(APISchema):
    """Produs cu vânzări mari în portofoliu, dar 0 vânzări la magazinul țintă."""
    product_id: UUID
    product_code: str
    product_name: str
    category: str | None
    listed_in_stores: int        # câte magazine din scope îl vând
    total_stores: int            # total magazine din scope cu vânzări în fereastră
    monthly_avg_per_listed: Decimal  # vânzare medie / lună / magazin care îl listează
    estimated_window_revenue: Decimal   # estimare pe `months_window` (valoare lei)
    estimated_window_quantity: Decimal  # estimare pe `months_window` (cantitate)
    estimated_12m_revenue: Decimal      # estimare anuală la magazinul țintă
    rationale: str               # explicație scurtă în RO


class AMInsightsResponse(APISchema):
    scope: str
    store: str                   # numele magazinului (RawSale.client)
    chain: str
    months_window: int
    rank_by_value: AMRank
    rank_by_skus: AMRank
    store_total_value: Decimal   # vânzările totale ale magazinului în fereastră
    store_sku_count: int         # SKU-uri unice vândute la magazin
    must_list: list[AMMustListProduct] = Field(default_factory=list)
