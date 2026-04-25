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
    # manual_quantities: {product_id: qty} — qty trimisa ca string ca sa pastram
    # precizia (Decimal serializat ca string in JSONB).
    manual_quantities: dict[str, str] | None = None
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
    manual_quantities: dict[str, str] | None = None
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


class PromoSimProductRow(APISchema):
    product_id: UUID
    code: str
    name: str
    category_label: str | None = None
    group_label: str
    group_kind: str
    group_key: str
    baseline_quantity: Decimal
    suggested_quantity: Decimal  # = baseline_quantity, expus explicit pentru UI
    used_quantity: Decimal       # qty efectiv folosit (manual sau baseline)
    is_manual: bool              # True daca user-ul a editat qty
    baseline_unit_price: Decimal
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


class PromoSimMonthlyRow(APISchema):
    year: int
    month: int
    month_label: str
    in_promo_period: bool
    # is_projected: True daca luna e in viitor si datele provin din proxy YoY
    # (luna corespondenta din anul anterior).
    is_projected: bool = False
    scope_baseline_revenue: Decimal
    scope_baseline_cost: Decimal
    scope_baseline_profit: Decimal
    scope_baseline_margin_pct: Decimal
    scope_scenario_revenue: Decimal
    scope_scenario_cost: Decimal
    scope_scenario_profit: Decimal
    scope_scenario_margin_pct: Decimal


class PromoSimRequest(APISchema):
    baseline_kind: str = "yoy"  # 'yoy' | 'mom'
    # Override per-call. Daca lipseste, se foloseste manual_quantities salvat
    # pe promotie. Daca si acela lipseste, se foloseste qty baseline.
    manual_quantities: dict[str, str] | None = None


class PromoSimResponse(APISchema):
    promotion_id: UUID
    baseline_kind: str  # 'yoy' | 'mom'
    baseline_label: str  # ex: "Iul-Sep 2025"
    promo_label: str     # ex: "Iul-Sep 2026"
    products_in_scope: int
    # Totaluri pe produsele din scope-ul promotiei
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
    # Totaluri pe TOT scope-ul KA (toate produsele, nu doar cele din promo) —
    # arata cum se schimba marja generala a scope-ului.
    scope_baseline_revenue: Decimal
    scope_baseline_cost: Decimal
    scope_baseline_profit: Decimal
    scope_baseline_margin_pct: Decimal
    scope_scenario_revenue: Decimal
    scope_scenario_cost: Decimal
    scope_scenario_profit: Decimal
    scope_scenario_margin_pct: Decimal
    scope_delta_revenue: Decimal
    scope_delta_profit: Decimal
    scope_delta_margin_pp: Decimal
    groups: list[PromoSimGroupRow] = Field(default_factory=list)
    products: list[PromoSimProductRow] = Field(default_factory=list)
    monthly: list[PromoSimMonthlyRow] = Field(default_factory=list)
