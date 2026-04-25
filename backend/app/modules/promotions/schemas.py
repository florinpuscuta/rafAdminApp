from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class PromotionTargetIn(APISchema):
    kind: str  # 'product' | 'category' | 'tm' | 'private_label' | 'all'
    key: str   # ignored when kind='all'


class PromotionTargetOut(PromotionTargetIn):
    id: UUID


class PromotionIn(APISchema):
    scope: str
    name: str
    status: str = "draft"  # 'draft' | 'active' | 'archived'
    discount_type: str  # 'pct' | 'override_price' | 'fixed_per_unit'
    value: Decimal
    valid_from: date
    valid_to: date
    client_filter: list[str] | None = None
    notes: str | None = None
    targets: list[PromotionTargetIn] = Field(default_factory=list)


class PromotionOut(APISchema):
    id: UUID
    scope: str
    name: str
    status: str
    discount_type: str
    value: Decimal
    valid_from: date
    valid_to: date
    client_filter: list[str] | None
    notes: str | None
    targets: list[PromotionTargetOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PromotionListResponse(APISchema):
    items: list[PromotionOut] = Field(default_factory=list)


# ── Simulare ───────────────────────────────────────────────────────────────


class PromoSimGroupRow(APISchema):
    label: str
    kind: str  # 'category' | 'tm' | 'private_label'
    key: str
    baseline_revenue: Decimal
    baseline_cost: Decimal
    baseline_profit: Decimal
    baseline_margin_pct: Decimal
    scenario_revenue: Decimal
    scenario_cost: Decimal
    scenario_profit: Decimal
    scenario_margin_pct: Decimal
    delta_revenue: Decimal
    delta_profit: Decimal
    delta_margin_pp: Decimal
    products_affected: int


class ProductSearchItem(APISchema):
    code: str
    name: str
    category_code: str | None = None
    category_label: str | None = None


class ProductSearchResponse(APISchema):
    items: list[ProductSearchItem] = Field(default_factory=list)


class GroupOption(APISchema):
    kind: str  # 'category' | 'tm' | 'private_label'
    key: str
    label: str


class GroupsResponse(APISchema):
    items: list[GroupOption] = Field(default_factory=list)


class PromoSimResponse(APISchema):
    promotion_id: UUID
    baseline_kind: str  # 'yoy' | 'mom'
    baseline_label: str  # ex: "Iul-Sep 2025"
    promo_label: str     # ex: "Iul-Sep 2026"
    products_in_scope: int
    baseline_revenue: Decimal
    baseline_cost: Decimal
    baseline_profit: Decimal
    baseline_margin_pct: Decimal
    scenario_revenue: Decimal
    scenario_cost: Decimal
    scenario_profit: Decimal
    scenario_margin_pct: Decimal
    delta_revenue: Decimal
    delta_profit: Decimal
    delta_margin_pp: Decimal
    groups: list[PromoSimGroupRow] = Field(default_factory=list)
