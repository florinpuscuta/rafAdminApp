from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class PPScope(APISchema):
    """Stari de stoc per scope: nr. produse cu pret + ultima incarcare."""

    scope: str
    count: int
    last_imported_at: datetime | None = None
    last_imported_filename: str | None = None


class PPSummaryResponse(APISchema):
    adp: PPScope
    sika: PPScope


class PPRow(APISchema):
    product_id: UUID
    product_code: str
    product_name: str
    category_label: str | None = None
    price: Decimal


class PPListResponse(APISchema):
    scope: str
    items: list[PPRow] = Field(default_factory=list)


class PPUploadResponse(APISchema):
    scope: str
    filename: str
    rows_total: int
    rows_matched: int
    rows_unmatched: int
    rows_invalid: int
    unmatched_codes: list[str] = Field(default_factory=list)
    inserted: int
    deleted_before: int = 0


# ── Snapshot lunar ─────────────────────────────────────────────────────────


from datetime import datetime  # noqa: E402


class PPMonthlySlot(APISchema):
    year: int
    month: int
    count: int
    last_imported_at: datetime | None = None


class PPMonthlySummaryResponse(APISchema):
    adp: list[PPMonthlySlot] = Field(default_factory=list)
    sika: list[PPMonthlySlot] = Field(default_factory=list)


class PPMonthlyListResponse(APISchema):
    scope: str
    year: int
    month: int
    items: list[PPRow] = Field(default_factory=list)


class PPMonthlyUploadResponse(APISchema):
    scope: str
    year: int
    month: int
    filename: str
    rows_total: int
    rows_matched: int
    rows_unmatched: int
    rows_invalid: int
    unmatched_codes: list[str] = Field(default_factory=list)
    inserted: int
    deleted_before: int = 0
