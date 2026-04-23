from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.schemas import APISchema


class MappingOut(APISchema):
    id: UUID
    source: str
    client_original: str
    ship_to_original: str
    agent_original: str | None
    cod_numeric: str | None
    cheie_finala: str
    agent_unificat: str
    store_id: UUID | None
    agent_id: UUID | None
    created_at: datetime
    updated_at: datetime


class IngestSummary(APISchema):
    rows_processed: int
    stores_created: int
    mappings_created: int
    mappings_updated: int


class IngestResponse(APISchema):
    summary: IngestSummary
    backfill_rows_updated: int


class MappingUpdate(APISchema):
    source: str | None = None
    client_original: str | None = None
    ship_to_original: str | None = None
    agent_original: str | None = None
    cod_numeric: str | None = None
    cheie_finala: str | None = None
    agent_unificat: str | None = None


class MappingCreate(APISchema):
    source: str
    client_original: str
    ship_to_original: str
    agent_original: str | None = None
    cod_numeric: str | None = None
    cheie_finala: str
    agent_unificat: str


class UnmappedClientRow(APISchema):
    client_original: str
    ship_to_original: str
    raw_client: str
    row_count: int
    total_sales: Decimal
    source: str
