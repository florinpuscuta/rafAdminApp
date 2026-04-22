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
