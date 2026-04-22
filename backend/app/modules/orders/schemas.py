from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class OrdersImportResponse(APISchema):
    inserted: int
    skipped: int
    deleted_before_insert: int = 0
    source: str
    report_date: str
    unmapped_clients: int = 0
    unmapped_products: int = 0
    errors: list[str] = Field(default_factory=list)


class OrdersImportJobAccepted(APISchema):
    job_id: UUID


class OrdersJobStageOut(APISchema):
    key: str
    label: str
    progress: float
    done: bool


class OrdersImportJobStatus(APISchema):
    id: UUID
    status: str
    stages: list[OrdersJobStageOut]
    current_stage: str | None = None
    overall_progress: float
    result: OrdersImportResponse | None = None
    error: str | None = None
    error_code: str | None = None
