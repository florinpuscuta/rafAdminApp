from uuid import UUID

from app.core.schemas import APISchema


class ProductCategoryOut(APISchema):
    id: UUID
    code: str
    label: str
    sort_order: int
