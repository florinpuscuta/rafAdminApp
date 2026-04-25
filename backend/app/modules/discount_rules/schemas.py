from pydantic import Field

from app.core.schemas import APISchema


class DRGroup(APISchema):
    """Element de matrice — o grupa (rand)."""
    kind: str  # 'category' | 'private_label' | 'tm'
    key: str   # category.code | 'marca_privata' | tm label
    label: str


class DRClient(APISchema):
    """Client KA (coloana)."""
    canonical: str
    label: str


class DRMatrixCell(APISchema):
    client_canonical: str
    group_kind: str
    group_key: str
    applies: bool


class DRMatrixResponse(APISchema):
    scope: str
    clients: list[DRClient] = Field(default_factory=list)
    groups: list[DRGroup] = Field(default_factory=list)
    cells: list[DRMatrixCell] = Field(default_factory=list)


class DRRuleIn(APISchema):
    client_canonical: str
    group_kind: str
    group_key: str
    applies: bool


class DRBulkUpsertRequest(APISchema):
    scope: str
    rules: list[DRRuleIn] = Field(default_factory=list)


class DRBulkUpsertResponse(APISchema):
    upserted: int
    deleted: int
