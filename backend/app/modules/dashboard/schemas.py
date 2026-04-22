from decimal import Decimal
from uuid import UUID

from app.core.schemas import APISchema


class OverviewKPIs(APISchema):
    total_rows: int
    total_amount: Decimal
    distinct_mapped_stores: int
    distinct_mapped_agents: int
    unmapped_store_rows: int
    unmapped_agent_rows: int


class TopStoreRow(APISchema):
    store_id: UUID | None
    store_name: str  # "Unmapped" dacă store_id=None
    chain: str | None
    total_amount: Decimal
    row_count: int


class TopAgentRow(APISchema):
    agent_id: UUID | None
    agent_name: str  # "Unmapped" dacă agent_id=None
    total_amount: Decimal
    row_count: int


class TopChainRow(APISchema):
    chain: str  # "Fără lanț" pentru stores fără chain, "Nemapate" pentru store_id=None
    total_amount: Decimal
    row_count: int
    store_count: int


class TopProductRow(APISchema):
    product_id: UUID | None
    product_code: str  # "Nemapate" dacă product_id=None
    product_name: str
    category: str | None
    total_amount: Decimal
    total_quantity: Decimal
    row_count: int


class MonthTotalRow(APISchema):
    month: int
    total_amount: Decimal
    row_count: int


class ScopeInfo(APISchema):
    """Echo al filtrelor scope — frontend-ul afișează breadcrumb-ul pe baza asta."""
    store_id: UUID | None = None
    store_name: str | None = None
    agent_id: UUID | None = None
    agent_name: str | None = None
    product_id: UUID | None = None
    product_code: str | None = None
    product_name: str | None = None


class DashboardOverview(APISchema):
    year: int | None
    month: int | None
    chain: str | None
    category: str | None
    scope: ScopeInfo | None
    available_years: list[int]
    kpis: OverviewKPIs
    top_stores: list[TopStoreRow]
    top_agents: list[TopAgentRow]
    monthly_totals: list[MonthTotalRow]
    top_chains: list[TopChainRow]
    top_products: list[TopProductRow]
    compare_year: int | None
    compare_kpis: OverviewKPIs | None
    monthly_totals_compare: list[MonthTotalRow]
