"""Scheme pentru endpoint-ul /api/rapoarte/word.

Corpul cererii e opțional — orice câmp lipsă folosește default-urile din
service (an curent, fără lună, fără lanț, fără scope îngust).
"""
from uuid import UUID

from app.core.schemas import APISchema


class RapoartWordRequest(APISchema):
    """Payload POST pentru generarea raportului Word.

    Toate câmpurile sunt opționale — fac filtrare similar cu
    /api/reports/dashboard.docx (care e GET). Preferăm POST aici pentru că
    frontend-ul poate trimite un scope mai bogat în viitor (ex. listă de
    lanțuri), fără să se lovească de limite de URL.
    """

    year: int | None = None
    month: int | None = None
    compare_year: int | None = None
    chain: str | None = None
    store_id: UUID | None = None
    agent_id: UUID | None = None
    product_id: UUID | None = None
