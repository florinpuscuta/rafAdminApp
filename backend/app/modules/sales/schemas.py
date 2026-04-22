from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class SaleOut(APISchema):
    id: UUID
    year: int
    month: int
    client: str
    channel: str | None
    product_code: str | None
    product_name: str | None
    category_code: str | None
    amount: Decimal
    quantity: Decimal | None
    agent: str | None
    store_id: UUID | None
    agent_id: UUID | None
    product_id: UUID | None
    created_at: datetime


class SalesListResponse(APISchema):
    items: list[SaleOut]
    total: int
    page: int
    page_size: int


class AlocareSummary(APISchema):
    rows_processed: int = 0
    agents_created: int = 0
    stores_created: int = 0
    store_aliases_created: int = 0
    agent_aliases_created: int = 0
    assignments_created: int = 0


class StoreAutocreate(APISchema):
    stores_created: int = 0
    aliases_created: int = 0
    rows_updated: int = 0


class BackfillSummary(APISchema):
    stores_exact_rows_updated: int = 0
    stores_autocreate: StoreAutocreate = Field(default_factory=StoreAutocreate)
    agents_via_store_rows_updated: int = 0


class ImportResponse(APISchema):
    inserted: int
    skipped: int
    deleted_before_insert: int = 0
    months_affected: list[str] = Field(default_factory=list)
    unmapped_clients: int = 0
    unmapped_agents: int = 0
    unmapped_products: int = 0
    alocare: AlocareSummary = Field(default_factory=AlocareSummary)
    backfill: BackfillSummary = Field(default_factory=BackfillSummary)
    errors: list[str] = Field(default_factory=list)


class ImportJobAccepted(APISchema):
    """Response pentru POST /import — uploadul a intrat în procesare async."""
    job_id: UUID


class JobStageOut(APISchema):
    key: str
    label: str
    progress: float
    done: bool


class ImportJobStatus(APISchema):
    id: UUID
    status: str  # pending | running | done | error
    stages: list[JobStageOut]
    current_stage: str | None = None
    overall_progress: float
    result: ImportResponse | None = None
    error: str | None = None
    error_code: str | None = None


class ImportBatchOut(APISchema):
    id: UUID
    filename: str
    source: str
    inserted_rows: int
    skipped_rows: int
    uploaded_by_user_id: UUID | None
    created_at: datetime
