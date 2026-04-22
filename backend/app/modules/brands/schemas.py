from uuid import UUID

from app.core.schemas import APISchema


class BrandOut(APISchema):
    id: UUID
    name: str
    is_private_label: bool
    sort_order: int


class BrandCreate(APISchema):
    name: str
    is_private_label: bool = False
    sort_order: int = 0
