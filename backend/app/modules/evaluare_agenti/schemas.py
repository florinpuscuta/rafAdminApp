from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


# ───────────────── Sal Fix (constantă per agent) ─────────────────

class AgentCompRow(APISchema):
    agent_id: UUID
    agent_name: str
    salariu_fix: Decimal = Field(default=Decimal("0"))
    note: str | None = None
    updated_at: datetime | None = None


class AgentCompList(APISchema):
    rows: list[AgentCompRow] = Field(default_factory=list)


class AgentCompUpsert(APISchema):
    agent_id: UUID
    salariu_fix: Decimal = Field(default=Decimal("0"))
    note: str | None = None


# ───────────────── Input Lunar (matrix cu costuri directe) ─────────────────

class MonthInputRow(APISchema):
    agent_id: UUID
    agent_name: str
    year: int
    month: int
    # Readonly (din pachet + /bonusari + /raion-bonus)
    vanzari: Decimal = Field(default=Decimal("0"))
    salariu_fix: Decimal = Field(default=Decimal("0"))
    bonus_agent: Decimal = Field(default=Decimal("0"))
    bonus_raion: Decimal = Field(default=Decimal("0"))
    # Editabile (direct RON)
    cost_combustibil: Decimal = Field(default=Decimal("0"))
    cost_revizii: Decimal = Field(default=Decimal("0"))
    alte_costuri: Decimal = Field(default=Decimal("0"))
    # Computed
    total_cost: Decimal = Field(default=Decimal("0"))
    note: str | None = None


class MonthInputList(APISchema):
    year: int
    month: int
    rows: list[MonthInputRow] = Field(default_factory=list)


class MonthInputUpsert(APISchema):
    agent_id: UUID
    year: int
    month: int
    cost_combustibil: Decimal = Field(default=Decimal("0"))
    cost_revizii: Decimal = Field(default=Decimal("0"))
    alte_costuri: Decimal = Field(default=Decimal("0"))
    note: str | None = None


# ───────────────── Zona Agent (bonus per magazin) ─────────────────

class ZonaStoreRow(APISchema):
    store_id: UUID
    store_name: str
    target: Decimal = Field(default=Decimal("0"))
    realizat: Decimal = Field(default=Decimal("0"))
    achievement_pct: Decimal | None = None
    bonus: Decimal = Field(default=Decimal("0"))
    note: str | None = None


class ZonaAgentSummary(APISchema):
    agent_id: UUID
    agent_name: str
    store_count: int = 0
    total_target: Decimal = Field(default=Decimal("0"))
    total_realizat: Decimal = Field(default=Decimal("0"))
    total_bonus: Decimal = Field(default=Decimal("0"))


class ZonaAgentsResponse(APISchema):
    year: int
    month: int
    agents: list[ZonaAgentSummary] = Field(default_factory=list)


class ZonaAgentDetail(APISchema):
    agent_id: UUID
    agent_name: str
    year: int
    month: int
    stores: list[ZonaStoreRow] = Field(default_factory=list)
    total_target: Decimal = Field(default=Decimal("0"))
    total_realizat: Decimal = Field(default=Decimal("0"))
    total_bonus: Decimal = Field(default=Decimal("0"))


class ZonaBonusUpsert(APISchema):
    agent_id: UUID
    store_id: UUID
    year: int
    month: int
    bonus: Decimal = Field(default=Decimal("0"))
    note: str | None = None


# ───────────────── Bonusări Oameni Raion (legacy) ─────────────────

class RaionBonusRow(APISchema):
    id: UUID
    store_id: UUID
    store_name: str
    agent_id: UUID | None
    agent_name: str | None
    year: int
    month: int
    contact_name: str
    suma: Decimal
    note: str | None = None


class RaionBonusList(APISchema):
    year: int
    month: int
    rows: list[RaionBonusRow] = Field(default_factory=list)
    total: Decimal = Field(default=Decimal("0"))


class RaionBonusCreate(APISchema):
    store_id: UUID
    year: int
    month: int
    contact_name: str
    suma: Decimal = Field(default=Decimal("0"))
    note: str | None = None


class RaionBonusUpdate(APISchema):
    contact_name: str
    suma: Decimal = Field(default=Decimal("0"))
    note: str | None = None


# ───────────────── Matricea Agenți ─────────────────

class MatrixRow(APISchema):
    agent_id: UUID
    agent_name: str
    vanzari: Decimal = Field(default=Decimal("0"))
    salariu_fix: Decimal = Field(default=Decimal("0"))
    bonus_agent: Decimal = Field(default=Decimal("0"))
    salariu_total: Decimal = Field(default=Decimal("0"))
    cost_combustibil: Decimal = Field(default=Decimal("0"))
    cost_revizii: Decimal = Field(default=Decimal("0"))
    alte_costuri: Decimal = Field(default=Decimal("0"))
    bonus_raion: Decimal = Field(default=Decimal("0"))
    total_cost: Decimal = Field(default=Decimal("0"))
    cost_per_100k: Decimal | None = None


class MatrixResponse(APISchema):
    year: int
    month: int
    rows: list[MatrixRow] = Field(default_factory=list)
    grand_vanzari: Decimal = Field(default=Decimal("0"))
    grand_cost: Decimal = Field(default=Decimal("0"))
