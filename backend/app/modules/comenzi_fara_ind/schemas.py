from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ProductLine(APISchema):
    product_code: str | None = None
    product_name: str | None = None
    quantity: Decimal
    remaining_quantity: Decimal
    amount: Decimal
    remaining_amount: Decimal


class OrderRow(APISchema):
    nr_comanda: str | None
    client_raw: str
    ship_to: str | None = None
    store_id: UUID | None = None
    store_name: str | None = None
    status: str | None = None
    data_livrare: str | None = None
    total_amount: Decimal
    total_remaining: Decimal
    line_items_count: int
    products: list[ProductLine] = Field(default_factory=list)


class AgentGroup(APISchema):
    agent_id: UUID | None
    agent_name: str
    orders_count: int
    total_amount: Decimal
    total_remaining: Decimal
    orders: list[OrderRow] = Field(default_factory=list)


class ComenziFaraIndResponse(APISchema):
    scope: str  # "adp" (pentru moment)
    report_date: date | None = None
    total_orders: int
    total_amount: Decimal
    total_remaining: Decimal
    agents: list[AgentGroup] = Field(default_factory=list)
