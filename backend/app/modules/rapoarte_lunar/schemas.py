"""Scheme pentru /api/rapoarte/lunar.

Sumele vin ca Decimal (serializate ca string, aceeași convenție ca
vz-la-zi / analiza-pe-luni). Diferențele procentuale pot fi None când
nu există bază de comparație (luna corespondentă în anul precedent = 0).
"""
from decimal import Decimal

from pydantic import Field

from app.core.schemas import APISchema


class RLKpis(APISchema):
    """Totaluri pentru luna curentă a raportului + comparație YoY."""

    total_amount: Decimal
    total_rows: int
    distinct_stores: int
    distinct_agents: int
    compare_amount: Decimal | None = None
    compare_rows: int | None = None
    pct_yoy: Decimal | None = None


class RLTopClient(APISchema):
    store_id: str | None = None
    store_name: str
    chain: str | None = None
    total_amount: Decimal


class RLTopAgent(APISchema):
    agent_id: str | None = None
    agent_name: str
    total_amount: Decimal


class RLChainRow(APISchema):
    chain: str
    store_count: int
    total_amount: Decimal


class RaportLunarResponse(APISchema):
    year: int
    month: int
    has_data: bool
    kpis: RLKpis
    top_clients: list[RLTopClient] = Field(default_factory=list)
    top_agents: list[RLTopAgent] = Field(default_factory=list)
    chains: list[RLChainRow] = Field(default_factory=list)
