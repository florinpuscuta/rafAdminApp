"""
Pydantic schemas pentru Facing Tracker — port 1:1 al payload-urilor legacy
`adeplast-dashboard/routes/facing.py`.

Răspunsurile JSON trebuie să rămână identice structural cu cele ale Flask-ului
vechi (camelCase via APISchema). UUID-urile SaaS sunt stringified (serializate
prin `str(uuid)`) — înlocuiesc INTEGER-urile legacy ale SQLite-ului.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class Raion(APISchema):
    id: UUID
    name: str
    sort_order: int = 0
    active: bool = True
    parent_id: UUID | None = None


class RaionTreeNode(APISchema):
    id: UUID
    name: str
    sort_order: int = 0
    active: bool = True
    parent_id: UUID | None = None
    children: list["RaionTreeNode"] = Field(default_factory=list)


class Brand(APISchema):
    id: UUID
    name: str
    color: str = "#888888"
    is_own: bool = False
    sort_order: int = 0
    active: bool = True


class ConfigResponse(APISchema):
    ok: bool = True
    raioane: list[Raion]
    raioane_tree: list[RaionTreeNode]
    brands: list[Brand]
    chain_brands: dict[str, list[UUID]]
    chains: list[str]


class OkResponse(APISchema):
    ok: bool = True


class TreeResponse(APISchema):
    ok: bool = True
    tree: list[RaionTreeNode]


class MigrateMonthBody(APISchema):
    luna: str


class MigrateDetail(APISchema):
    store_name: str
    from_raion_id: UUID
    to_raion_id: UUID
    brand_id: UUID
    nr_fete: int


class MigrateMonthResponse(APISchema):
    ok: bool = True
    migrated: int
    details: list[MigrateDetail]
    luna: str


class ChainBrandsResponse(APISchema):
    ok: bool = True
    chain_brands: dict[str, list[UUID]]
    chains: list[str]


class ChainBrandsSaveBody(APISchema):
    matrix: dict[str, list[UUID]]


class RaionCreateBody(APISchema):
    name: str
    parent_id: UUID | None = None


class RaionUpdateBody(APISchema):
    name: str


class BrandCreateBody(APISchema):
    name: str
    color: str = "#888888"


class BrandUpdateBody(APISchema):
    name: str
    color: str | None = None


class StoresResponse(APISchema):
    ok: bool = True
    stores: list[str]


class StoreDeleteResponse(APISchema):
    ok: bool = True
    deleted: int
    store: str
    luna: str | None = None


class Snapshot(APISchema):
    id: UUID
    store_name: str
    raion_id: UUID
    raion_name: str
    brand_id: UUID
    brand_name: str
    brand_color: str
    luna: str
    nr_fete: int
    updated_at: datetime | None = None
    updated_by: str | None = None


class SnapshotsResponse(APISchema):
    ok: bool = True
    data: list[Snapshot]


class SaveEntry(APISchema):
    store_name: str
    raion_id: UUID
    brand_id: UUID
    luna: str
    nr_fete: int = 0


class SaveBody(APISchema):
    store_name: str | None = None
    raion_id: UUID | None = None
    brand_id: UUID | None = None
    luna: str | None = None
    nr_fete: int | None = None
    entries: list[SaveEntry] = Field(default_factory=list)


class SaveResponse(APISchema):
    ok: bool = True
    saved: int


class EvolutionRow(APISchema):
    luna: str
    store_name: str
    raion_name: str
    raion_id: UUID
    brand_name: str
    brand_color: str
    brand_id: UUID
    nr_fete: int


class EvolutionResponse(APISchema):
    ok: bool = True
    data: list[EvolutionRow]


class BrandSummary(APISchema):
    brand_id: UUID
    brand_name: str
    brand_color: str
    total_fete: int
    avg_fete: float
    prev_avg_fete: float
    delta_avg: float
    pct: float


class ChainSummary(APISchema):
    chain: str
    nr_magazine: int
    prev_nr_magazine: int
    total_fete_all: int
    avg_fete_all: float
    own_pct_weighted: float
    prev_own_pct_weighted: float
    own_pct_delta: float
    own_total_fete: int
    own_stores_counted: int
    brands_summary: list[BrandSummary]
    stores: dict[str, dict]


class CompetitorGlobal(APISchema):
    brand_id: UUID
    brand_name: str
    brand_color: str
    total_fete: int
    pct: float
    pct_arith: float
    prev_pct: float
    prev_pct_arith: float
    delta_pp: float
    delta_pp_arith: float


class DashboardResponse(APISchema):
    ok: bool = True
    luna: str
    prev_luna: str
    chains: list[ChainSummary]
    total_chains: int
    global_total_fete: int
    global_own_total_fete: int
    global_own_pct_weighted: float
    global_prev_own_pct_weighted: float
    global_own_pct_delta: float
    global_own_pct_arith: float
    global_prev_own_pct_arith: float
    global_own_pct_arith_delta: float
    global_stores_counted_arith: int
    global_competitors: list[CompetitorGlobal]
    total_magazine: int


class MonthsResponse(APISchema):
    ok: bool = True
    months: list[str]


# ── Dash Face Tracker: cota-parte per sub-raion ─────────────────────────────

class RaionBrandShare(APISchema):
    brand_id: UUID | None = None  # None pentru "Alții"
    brand_name: str
    brand_color: str
    total_fete: int
    pct: float
    category: str  # "own" | "competitor" | "other"


class ChainRaionShare(APISchema):
    """Cota pe o rețea client (Dedeman/Altex/Leroy Merlin/Hornbach/Alte),
    pentru același sub_raion."""
    chain: str
    total_fete: int
    own_fete: int
    own_pct: float
    brands: list[RaionBrandShare]


class SubRaionShare(APISchema):
    raion_id: UUID
    raion_name: str
    total_fete: int
    own_fete: int
    own_pct: float
    brands: list[RaionBrandShare]
    chains: list[ChainRaionShare] = Field(default_factory=list)


class ParentRaionShare(APISchema):
    parent_id: UUID
    parent_name: str
    total_fete: int
    own_fete: int
    own_pct: float
    sub_raioane: list[SubRaionShare]


class RaionShareAnalysis(APISchema):
    scope: str  # "adp" | "sika"
    own_brand_name: str
    competitor_names: list[str]
    parents: list[ParentRaionShare]
    global_total_fete: int
    global_own_fete: int
    global_own_pct: float


class RaionShareResponse(APISchema):
    ok: bool = True
    luna: str
    requested_scope: str  # "adp" | "sika" | "sikadp"
    analyses: list[RaionShareAnalysis]


# ── Matrice concurențe configurabile (own × competitor × sub_raion) ─────────

class RaionCompetitorEntry(APISchema):
    raion_id: UUID
    own_brand_id: UUID
    competitor_brand_id: UUID
    sort_order: int = 0


class RaionCompetitorsMatrix(APISchema):
    """Matricea plată: listă de (raion, own, competitor) bifate."""
    ok: bool = True
    entries: list[RaionCompetitorEntry]


class RaionCompetitorsSaveBody(APISchema):
    """Salvează lista completă — orice entry existent care NU apare aici e șters."""
    entries: list[RaionCompetitorEntry] = Field(default_factory=list)
