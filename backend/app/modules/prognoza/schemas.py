from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class PrognozaHistoryPoint(APISchema):
    """Un punct din istoric (lună completă cu vânzări)."""
    year: int
    month: int                          # 1..12
    month_name: str                     # "Ianuarie"..."Decembrie"
    label: str                          # "Ian 2025"
    sales: Decimal


class PrognozaForecastPoint(APISchema):
    """Un punct din viitor (predicție)."""
    year: int
    month: int                          # 1..12
    month_name: str                     # "Ianuarie"..."Decembrie"
    label: str                          # "Mai 2026"
    forecast_sales: Decimal             # valoarea prognozată
    moving_avg: Decimal                 # media mobilă ultimele 3 luni
    seasonal_factor: Decimal | None     # factor sezonal (vs same-month PY), None daca PY lipseste
    trend_pct: Decimal | None           # % linear regression lookback 12 luni, None daca date insuficiente


class PrognozaAgentRow(APISchema):
    """Un rand per agent: total istoric + forecast pe orizont."""
    agent_id: UUID | None
    agent_name: str
    history_total: Decimal              # suma vânzări ultimele 12 luni
    forecast_total: Decimal             # suma forecast pe orizont
    forecast_months: list[Decimal] = Field(default_factory=list)  # len == horizon_months


class PrognozaResponse(APISchema):
    scope: str                          # "adp" | "sika" | "sikadp"
    horizon_months: int
    method: str                         # "moving_avg_3m_with_seasonal" | "moving_avg_3m"
    last_update: datetime | None = None
    last_complete_month: str | None = None  # "Aprilie 2026"
    history: list[PrognozaHistoryPoint] = Field(default_factory=list)  # ultimele 12 luni
    forecast: list[PrognozaForecastPoint] = Field(default_factory=list)  # horizon_months
    agents: list[PrognozaAgentRow] = Field(default_factory=list)
