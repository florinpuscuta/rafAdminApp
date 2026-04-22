from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class StoreOut(APISchema):
    id: UUID
    name: str
    chain: str | None
    city: str | None
    active: bool
    created_at: datetime


class CreateStoreRequest(APISchema):
    name: str = Field(min_length=1, max_length=255)
    chain: str | None = None
    city: str | None = None


class StoreAliasOut(APISchema):
    id: UUID
    raw_client: str
    store_id: UUID
    resolved_by_user_id: UUID | None
    resolved_at: datetime


class CreateAliasRequest(APISchema):
    raw_client: str = Field(min_length=1, max_length=255)
    store_id: UUID


class UpdateAliasRequest(APISchema):
    store_id: UUID  # reasignează la alt magazin canonic


class UnmappedClientRow(APISchema):
    raw_client: str
    row_count: int
    total_amount: Decimal


class SuggestedMatch(APISchema):
    store_id: UUID
    store_name: str
    score: float


class SuggestionRow(APISchema):
    raw_client: str
    suggestions: list[SuggestedMatch]


class BulkImportResponse(APISchema):
    created_stores: int
    created_aliases: int
    skipped: int
    errors: list[str]


class MergeStoresRequest(APISchema):
    primary_id: UUID
    duplicate_ids: list[UUID] = Field(min_length=1)


class MergeStoresResponse(APISchema):
    primary_id: UUID
    merged_count: int
    aliases_reassigned: int
    sales_reassigned: int
    assignments_reassigned: int
    assignments_deduped: int


class BulkSetActiveRequest(APISchema):
    ids: list[UUID] = Field(min_length=1, max_length=500)
    active: bool


class BulkSetActiveResponse(APISchema):
    updated: int
