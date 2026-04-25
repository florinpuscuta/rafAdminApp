"""Router pentru /api/rapoarte/word.

POST /api/rapoarte/word — corpul e `RapoartWordRequest` (toate câmpurile opționale).
Răspuns: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
streaming, cu `Content-Disposition: attachment`.

De ce POST: față de /api/reports/dashboard.docx (GET, legacy), aici avem
un contract explicit via schema pydantic și rezervăm loc pentru scope-uri
mai bogate în viitor (listă de lanțuri, interval custom).
"""
from io import BytesIO
from uuid import UUID

from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.rapoarte_word import service as svc
from app.modules.rapoarte_word.schemas import RapoartWordRequest

router = APIRouter(prefix="/api/rapoarte/word", tags=["rapoarte-word"])


@router.post("")
async def generate_raport_word(
    body: RapoartWordRequest | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Generare per orga activa (resolved via X-Active-Org-Id header).
    In SIKADP consolidated mode pickeaza orga default; UI-ul indicator banner.
    """
    req = body or RapoartWordRequest()
    docx_bytes, filename = await svc.generate_docx(
        session, tenant_id,
        year=req.year, month=req.month, compare_year=req.compare_year,
        chain=req.chain, store_id=req.store_id, agent_id=req.agent_id,
        product_id=req.product_id,
    )
    buf = BytesIO(docx_bytes)
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
