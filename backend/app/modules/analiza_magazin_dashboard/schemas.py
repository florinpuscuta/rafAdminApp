from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class AMDClientsResponse(APISchema):
    clients: list[str] = Field(default_factory=list)


class AMDStoreOption(APISchema):
    store_id: UUID
    name: str


class AMDStoresResponse(APISchema):
    client: str
    stores: list[AMDStoreOption] = Field(default_factory=list)


class AMDMetrics(APISchema):
    sales: Decimal
    quantity: Decimal
    sku_count: int


class AMDMonthSeries(APISchema):
    year: int
    month: int
    sales_curr: Decimal
    sales_prev_year: Decimal
    sku_curr: int
    sku_prev_year: int


class AMDCategoryRow(APISchema):
    code: str
    label: str
    curr: AMDMetrics
    yoy: AMDMetrics


class AMDBrandSplit(APISchema):
    brand: AMDMetrics
    private_label: AMDMetrics
    brand_yoy: AMDMetrics
    private_label_yoy: AMDMetrics


class AMDPair(APISchema):
    year: int
    month: int


class AMDDashboardResponse(APISchema):
    scope: str
    store_id: UUID
    store_name: str
    months_window: int
    window_curr: list[AMDPair] = Field(default_factory=list)
    window_yoy: list[AMDPair] = Field(default_factory=list)
    window_prev: list[AMDPair] = Field(default_factory=list)
    kpi_curr: AMDMetrics
    kpi_yoy: AMDMetrics
    kpi_prev: AMDMetrics
    monthly: list[AMDMonthSeries] = Field(default_factory=list)
    categories: list[AMDCategoryRow] = Field(default_factory=list)
    brand_split: AMDBrandSplit
