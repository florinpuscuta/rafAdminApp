"""
Catalog Lunar router — port 1:1 din legacy `routes/gallery.py` (gallery_type='catalog').

Endpoint-urile păstrează paths + params + shapes ca legacy, adaptate la prefix
`/api/marketing/catalog`.
"""
from uuid import UUID

from fastapi import Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import (
    get_current_org_ids,
    get_current_tenant_id,
    get_current_user,
)
from app.modules.gallery import service as gallery_svc
from app.modules.mkt_catalog import service as svc
from app.modules.mkt_catalog.schemas import (
    CatalogFolderDetailResponse,
    CatalogFolderListResponse,
    CatalogFolderOut,
    CatalogPhotoOut,
    CreateCatalogFolderRequest,
    MktCatalogResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/marketing/catalog", tags=["marketing-catalog"])

# Limitări legacy: 15 MB, tipuri pe care browser-ul le poate randa (legacy avea
# compresie Pillow — în SaaS păstrăm originalul, MinIO are spațiu).
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


# ───────────── Listare luni (foldere) ─────────────

@router.get("", response_model=MktCatalogResponse)
async def list_catalog(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> MktCatalogResponse:
    """Compat cu ecranul placeholder (tests)."""
    data = await svc.list_items_by_tenants(session, org_ids)
    return MktCatalogResponse.model_validate(data)


@router.get("/folders", response_model=CatalogFolderListResponse)
async def list_folders(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> CatalogFolderListResponse:
    folders = await svc.list_folders_with_cover_by_tenants(session, org_ids)
    notice = None
    if not folders:
        notice = 'Nu există încă cataloage — adaugă o lună nouă (buton „+ Lună Nouă").'
    return CatalogFolderListResponse(
        folders=[CatalogFolderOut.model_validate(f) for f in folders],
        notice=notice,
    )


@router.post(
    "/folders",
    response_model=CatalogFolderOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(
    request: Request,
    payload: CreateCatalogFolderRequest,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> CatalogFolderOut:
    """Mirror peste `api_gallery_create_folder('catalog')`.

    Convenție legacy: numele reprezintă o lună („Ianuarie 2026" sau „2026-01").
    """
    try:
        folder = await gallery_svc.create_folder(
            session,
            tenant_id=tenant_id,
            type_=svc.GALLERY_TYPE,
            name=payload.name.strip(),
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "folder_exists", "message": "Folderul există deja"},
        )
    await audit_service.log_event(
        session,
        event_type="mkt_catalog.folder.created",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="gallery_folder",
        target_id=folder.id,
        metadata={"type": folder.type, "name": folder.name},
        request=request,
    )
    return CatalogFolderOut(
        id=folder.id,
        name=folder.name,
        month=svc._extract_month(folder.name),
        photo_count=0,
        cover_url=None,
        created_at=folder.created_at,
    )


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    request: Request,
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Mirror peste `api_gallery_delete_folder('catalog', name)`."""
    folder = None
    owner_tenant_id: UUID | None = None
    for tid in org_ids:
        folder = await gallery_svc.get_folder(session, tid, folder_id)
        if folder is not None and folder.type == svc.GALLERY_TYPE:
            owner_tenant_id = tid
            break
    if folder is None or owner_tenant_id is None or folder.type != svc.GALLERY_TYPE:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "folder_not_found", "message": "Luna nu există"},
        )
    count = await gallery_svc.delete_folder(session, folder)
    await audit_service.log_event(
        session,
        event_type="mkt_catalog.folder.deleted",
        tenant_id=owner_tenant_id,
        user_id=current_user.id,
        target_type="gallery_folder",
        target_id=folder_id,
        metadata={"name": folder.name, "photos_deleted": count},
        request=request,
    )
    return None


# ───────────── Poze per folder ─────────────

@router.get(
    "/folders/{folder_id}/photos",
    response_model=CatalogFolderDetailResponse,
)
async def list_photos(
    folder_id: UUID,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> CatalogFolderDetailResponse:
    folder = None
    owner_tenant_id: UUID | None = None
    for tid in org_ids:
        folder = await gallery_svc.get_folder(session, tid, folder_id)
        if folder is not None and folder.type == svc.GALLERY_TYPE:
            owner_tenant_id = tid
            break
    if folder is None or owner_tenant_id is None or folder.type != svc.GALLERY_TYPE:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "folder_not_found", "message": "Luna nu există"},
        )
    photos = await svc.list_photos_for_folder(session, owner_tenant_id, folder_id)
    return CatalogFolderDetailResponse(
        folder_id=folder.id,
        folder_name=folder.name,
        month=svc._extract_month(folder.name),
        photos=[CatalogPhotoOut.model_validate(p) for p in photos],
    )


@router.post(
    "/folders/{folder_id}/photos",
    response_model=CatalogPhotoOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    request: Request,
    folder_id: UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> CatalogPhotoOut:
    """Mirror peste `api_gallery_upload('catalog', folder)`.

    Legacy avea compresie Pillow + thumbnail; în SaaS păstrăm originalul
    (MinIO gestionează storage), iar thumb_url = url în response.
    """
    folder = None
    owner_tenant_id: UUID | None = None
    for tid in org_ids:
        folder = await gallery_svc.get_folder(session, tid, folder_id)
        if folder is not None and folder.type == svc.GALLERY_TYPE:
            owner_tenant_id = tid
            break
    if folder is None or owner_tenant_id is None or folder.type != svc.GALLERY_TYPE:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "folder_not_found", "message": "Luna nu există"},
        )

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_content_type",
                "message": f"Se acceptă doar {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
            },
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fișier gol"},
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "file_too_large",
                "message": f"Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            },
        )

    photo = await gallery_svc.upload_photo(
        session,
        tenant_id=owner_tenant_id,
        folder=folder,
        filename=file.filename or "untitled",
        content=content,
        content_type=content_type,
        uploaded_by_user_id=current_user.id,
    )
    await audit_service.log_event(
        session,
        event_type="mkt_catalog.photo.uploaded",
        tenant_id=owner_tenant_id,
        user_id=current_user.id,
        target_type="gallery_photo",
        target_id=photo.id,
        metadata={
            "folder_id": str(folder.id),
            "filename": photo.filename,
            "size_bytes": photo.size_bytes,
        },
        request=request,
    )
    url = gallery_svc.photo_url(photo)
    return CatalogPhotoOut(
        id=photo.id,
        folder_id=photo.folder_id,
        filename=photo.filename,
        size_kb=round(photo.size_bytes / 1024, 1),
        caption=photo.caption,
        uploaded_by_user_id=photo.uploaded_by_user_id,
        uploaded_at=photo.uploaded_at,
        url=url,
        thumb_url=url,
    )


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    request: Request,
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Mirror peste `api_gallery_delete_image('catalog', folder, filename)`."""
    photo = None
    owner_tenant_id: UUID | None = None
    for tid in org_ids:
        photo = await gallery_svc.get_photo(session, tid, photo_id)
        if photo is not None:
            owner_tenant_id = tid
            break
    if photo is None or owner_tenant_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poză inexistentă"},
        )
    # Siguranță: permitem ștergerea doar dacă folder-ul e de tip catalog
    folder = await gallery_svc.get_folder(session, owner_tenant_id, photo.folder_id)
    if folder is None or folder.type != svc.GALLERY_TYPE:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poză inexistentă"},
        )
    filename = photo.filename
    await gallery_svc.delete_photo(session, photo)
    await audit_service.log_event(
        session,
        event_type="mkt_catalog.photo.deleted",
        tenant_id=owner_tenant_id,
        user_id=current_user.id,
        target_type="gallery_photo",
        target_id=photo_id,
        metadata={"filename": filename},
        request=request,
    )
    return None
