from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ProductOut(APISchema):
    id: UUID
    code: str
    name: str
    category: str | None
    brand: str | None
    active: bool
    created_at: datetime


class CreateProductRequest(APISchema):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    category: str | None = None
    brand: str | None = None


class ProductAliasOut(APISchema):
    id: UUID
    raw_code: str
    product_id: UUID
    resolved_by_user_id: UUID | None
    resolved_at: datetime


class CreateProductAliasRequest(APISchema):
    raw_code: str = Field(min_length=1, max_length=100)
    product_id: UUID


class UpdateProductAliasRequest(APISchema):
    product_id: UUID


class BulkImportResponse(APISchema):
    created_products: int
    created_aliases: int
    skipped: int
    errors: list[str]


class UnmappedProductRow(APISchema):
    raw_code: str
    sample_name: str | None  # primul product_name găsit pentru orientare vizuală
    row_count: int
    total_amount: Decimal


class MergeProductsRequest(APISchema):
    primary_id: UUID
    duplicate_ids: list[UUID] = Field(min_length=1)


class MergeProductsResponse(APISchema):
    primary_id: UUID
    merged_count: int
    aliases_reassigned: int
    sales_reassigned: int


class BulkSetActiveRequest(APISchema):
    ids: list[UUID] = Field(min_length=1, max_length=500)
    active: bool


class BulkSetActiveResponse(APISchema):
    updated: int
