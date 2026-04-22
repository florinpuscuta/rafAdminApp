"""Helpers partajate între test files (generare xlsx, etc)."""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Any, Sequence

from openpyxl import Workbook


DEFAULT_HEADERS = [
    "year",
    "month",
    "client",
    "channel",
    "product_code",
    "product_name",
    "category_code",
    "amount",
    "quantity",
    "agent",
]


def make_xlsx(
    rows: Sequence[dict[str, Any]],
    headers: Sequence[str] = DEFAULT_HEADERS,
) -> bytes:
    """Construiește un .xlsx in-memory cu `headers` ca prim rând urmate de rows."""
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def sample_row(
    *,
    year: int = 2026,
    month: int = 3,
    client: str = "DEDEMAN SRL",
    amount: Decimal | float | int = 1000,
    product_code: str | None = "SKU-001",
    product_name: str | None = "Adeziv Placi",
    agent: str | None = "Ionut Filip",
    channel: str | None = "retail",
    category_code: str | None = "A1",
    quantity: Decimal | float | int | None = 10,
) -> dict[str, Any]:
    return {
        "year": year,
        "month": month,
        "client": client,
        "channel": channel,
        "product_code": product_code,
        "product_name": product_name,
        "category_code": category_code,
        "amount": amount,
        "quantity": quantity,
        "agent": agent,
    }
