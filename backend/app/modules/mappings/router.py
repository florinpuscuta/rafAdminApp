from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_user
from app.modules.mappings import service
from app.modules.mappings.schemas import (
    IngestResponse,
    IngestSummary,
    MappingCreate,
    MappingOut,
    MappingUpdate,
    UnmappedClientRow,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/mappings", tags=["mappings"])


@router.get("", response_model=list[MappingOut])
async def list_mappings(
    source: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await service.list_mappings(
        session, current_user.tenant_id, source=source,
    )
    return [MappingOut.model_validate(r) for r in rows]


@router.get("/unmapped", response_model=list[UnmappedClientRow])
async def list_unmapped(
    scope: str = Query("adp", description="adp sau sika"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Distinct (client, ship_to) din raw_sales KA care nu sunt în SAM —
    pentru UI de alocare rapidă a agenților.
    """
    rows = await service.list_unmapped_clients(
        session, current_user.tenant_id, scope=scope,
    )
    return [UnmappedClientRow.model_validate(r) for r in rows]


@router.post("/upload", response_model=IngestResponse)
async def upload_mapping(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload fișierului `mapare_completa_magazine_cu_coduri_v2.xlsx`.
    Upsert în store_agent_mappings + creare canonicals + backfill raw_sales.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Doar .xlsx"},
        )
    content = await file.read()
    try:
        rows = service.parse_mapping_xlsx(content)
    except ValueError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "parse_error", "message": str(e)},
        )

    try:
        summary = await service.ingest_mapping_rows(
            session, current_user.tenant_id, rows,
        )
    except service.UnknownAgentError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "unknown_agent", "message": str(e)},
        )
    backfill = await service.backfill_raw_sales(
        session, current_user.tenant_id, source="ADP",
    )
    await session.commit()

    await audit_service.log_event(
        session,
        event_type="mappings.uploaded",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="tenant",
        target_id=current_user.tenant_id,
        metadata={"filename": filename, "summary": str(summary)[:500]},
        request=request,
    )
    await session.commit()

    return IngestResponse(
        summary=IngestSummary(**summary),
        backfill_rows_updated=backfill["rows_updated"],
    )


@router.post("", response_model=MappingOut, status_code=201)
async def create_mapping(
    payload: MappingCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        m = await service.create_mapping(
            session, current_user.tenant_id, payload.model_dump(),
        )
    except service.UnknownAgentError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "unknown_agent", "message": str(e)},
        )
    backfill = await service.backfill_raw_sales(
        session, current_user.tenant_id, source=m.source,
    )
    await session.commit()
    await session.refresh(m)

    await audit_service.log_event(
        session,
        event_type="mappings.created",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="store_agent_mapping",
        target_id=m.id,
        metadata={"rows_rebackfilled": backfill["rows_updated"]},
        request=request,
    )
    await session.commit()
    return MappingOut.model_validate(m)


@router.patch("/{mapping_id}", response_model=MappingOut)
async def update_mapping(
    mapping_id: UUID,
    payload: MappingUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        m = await service.update_mapping(
            session, current_user.tenant_id, mapping_id,
            payload.model_dump(exclude_unset=True),
        )
    except service.UnknownAgentError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "unknown_agent", "message": str(e)},
        )
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mapping inexistent")
    backfill = await service.backfill_raw_sales(
        session, current_user.tenant_id, source=m.source,
    )
    await session.commit()
    await session.refresh(m)

    await audit_service.log_event(
        session,
        event_type="mappings.updated",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="store_agent_mapping",
        target_id=m.id,
        metadata={"rows_rebackfilled": backfill["rows_updated"]},
        request=request,
    )
    await session.commit()
    return MappingOut.model_validate(m)


@router.delete("/{mapping_id}", status_code=204)
async def delete_mapping(
    mapping_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ok = await service.delete_mapping(
        session, current_user.tenant_id, mapping_id,
    )
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mapping inexistent")
    backfill = await service.backfill_raw_sales(
        session, current_user.tenant_id, source="ADP",
    )
    await session.commit()

    await audit_service.log_event(
        session,
        event_type="mappings.deleted",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="store_agent_mapping",
        target_id=mapping_id,
        metadata={"rows_rebackfilled": backfill["rows_updated"]},
        request=request,
    )
    await session.commit()
