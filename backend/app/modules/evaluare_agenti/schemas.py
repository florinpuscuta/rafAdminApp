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
    bonus_vanzari_eligibil: bool = True
    note: str | None = None
    updated_at: datetime | None = None


class AgentCompList(APISchema):
    rows: list[AgentCompRow] = Field(default_factory=list)


class AgentCompUpsert(APISchema):
    agent_id: UUID
    salariu_fix: Decimal = Field(default=Decimal("0"))
    bonus_vanzari_eligibil: bool = True
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
    merchandiser_zona: Decimal = Field(default=Decimal("0"))
    cheltuieli_auto: Decimal = Field(default=Decimal("0"))
    alte_cheltuieli: Decimal = Field(default=Decimal("0"))
    alte_cheltuieli_label: str | None = None
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
    merchandiser_zona: Decimal = Field(default=Decimal("0"))
    cheltuieli_auto: Decimal = Field(default=Decimal("0"))
    alte_cheltuieli: Decimal = Field(default=Decimal("0"))
    alte_cheltuieli_label: str | None = None
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


# ───────────────── Analiza costuri anuală ─────────────────

class AnnualCostRow(APISchema):
    agent_id: UUID
    agent_name: str
    monthly: list[Decimal] = Field(default_factory=list)
    total: Decimal = Field(default=Decimal("0"))


class AnnualCostResponse(APISchema):
    year: int
    rows: list[AnnualCostRow] = Field(default_factory=list)
    month_totals: list[Decimal] = Field(default_factory=list)
    grand_total: Decimal = Field(default=Decimal("0"))


class AgentAnnualMonthRow(APISchema):
    month: int
    salariu_fix: Decimal = Field(default=Decimal("0"))
    bonus_agent: Decimal = Field(default=Decimal("0"))
    merchandiser_zona: Decimal = Field(default=Decimal("0"))
    cheltuieli_auto: Decimal = Field(default=Decimal("0"))
    alte_cheltuieli: Decimal = Field(default=Decimal("0"))
    bonus_raion: Decimal = Field(default=Decimal("0"))
    total: Decimal = Field(default=Decimal("0"))


class AgentAnnualResponse(APISchema):
    agent_id: UUID
    agent_name: str
    year: int
    rows: list[AgentAnnualMonthRow] = Field(default_factory=list)
    column_totals: AgentAnnualMonthRow


# ───────────────── Dashboard agenți ─────────────────

class DashboardAgentRow(APISchema):
    agent_id: UUID
    agent_name: str
    store_count: int = 0
    vanzari: Decimal = Field(default=Decimal("0"))
    vanzari_prev: Decimal = Field(default=Decimal("0"))
    cheltuieli: Decimal = Field(default=Decimal("0"))
    cost_pct: Decimal | None = None
    cost_per_100k: Decimal | None = None
    yoy_pct: Decimal | None = None
    bonus_agent: Decimal = Field(default=Decimal("0"))


class DashboardResponse(APISchema):
    year: int
    month: int | None = None
    rows: list[DashboardAgentRow] = Field(default_factory=list)
    grand_vanzari: Decimal = Field(default=Decimal("0"))
    grand_cheltuieli: Decimal = Field(default=Decimal("0"))
    grand_bonus_agent: Decimal = Field(default=Decimal("0"))
    grand_store_count: int = 0
    grand_cost_pct: Decimal | None = None


class BonusMagazinAnnualRow(APISchema):
    agent_id: UUID
    agent_name: str
    monthly: list[Decimal] = Field(default_factory=list)
    total: Decimal = Field(default=Decimal("0"))


class BonusMagazinAnnualResponse(APISchema):
    year: int
    rows: list[BonusMagazinAnnualRow] = Field(default_factory=list)
    month_totals: list[Decimal] = Field(default_factory=list)
    grand_total: Decimal = Field(default=Decimal("0"))


class SalariuBonusAnnualRow(APISchema):
    agent_id: UUID
    agent_name: str
    monthly: list[Decimal] = Field(default_factory=list)
    total: Decimal = Field(default=Decimal("0"))


class SalariuBonusAnnualResponse(APISchema):
    year: int
    rows: list[SalariuBonusAnnualRow] = Field(default_factory=list)
    month_totals: list[Decimal] = Field(default_factory=list)
    grand_total: Decimal = Field(default=Decimal("0"))


# ───────────────── Facturi Bonus de Asignat ─────────────────

class FacturaBonusRow(APISchema):
    id: UUID
    year: int
    month: int
    amount: Decimal
    client: str
    chain: str | None = None
    # Starea curentă a rândului în raw_sales
    agent_id: UUID | None = None
    agent_name: str | None = None
    store_id: UUID | None = None
    store_name: str | None = None
    # Sugestia (target) pentru reasignare
    suggested_store_id: UUID | None = None
    suggested_store_name: str | None = None
    suggested_agent_id: UUID | None = None
    suggested_agent_name: str | None = None
    # Status: "pending" (roșu, de asignat) sau "assigned" (verde, deja decis)
    status: str = "pending"
    decided_at: datetime | None = None
    decision_source: str | None = None  # "auto" / "manual" / None dacă pending


class FacturaBonusPendingCount(APISchema):
    pending_count: int = 0
    pending_amount: Decimal = Field(default=Decimal("0"))


class FacturaBonusList(APISchema):
    rows: list[FacturaBonusRow] = Field(default_factory=list)
    pending_count: int = 0
    pending_amount: Decimal = Field(default=Decimal("0"))
    assigned_count: int = 0
    assigned_amount: Decimal = Field(default=Decimal("0"))
    threshold: Decimal = Field(default=Decimal("-20000"))


class FacturaBonusAcceptRequest(APISchema):
    ids: list[UUID]


class FacturaBonusAcceptResponse(APISchema):
    accepted: int
    skipped: int


class FacturaBonusUnassignRequest(APISchema):
    ids: list[UUID]


class FacturaBonusUnassignResponse(APISchema):
    unassigned: int
    skipped: int
