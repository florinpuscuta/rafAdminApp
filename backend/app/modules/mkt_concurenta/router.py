"""
Router Acțiuni Concurență — port 1:1 al endpoint-urilor legacy:

  legacy                                              → SaaS
  GET    /api/gallery/folders/concurenta              → GET /api/marketing/concurenta?year=YYYY
  POST   /api/gallery/folders/concurenta              → POST /api/marketing/concurenta/folders (body: year+month)
  GET    /api/gallery/concurenta/<folderKey>          → GET /api/marketing/concurenta/months/<YYYY_MM>/photos
  POST   /api/gallery/concurenta/<folderKey>          → POST /api/marketing/concurenta/months/<YYYY_MM>/photos
  DELETE /api/gallery/concurenta/<folderKey>/<file>   → DELETE /api/marketing/concurenta/photos/<photo_id>
  POST   /api/gallery/concurenta/<folderKey>/<file>/rotate → POST /api/marketing/concurenta/photos/<photo_id>/rotate

Rotate foloseste Pillow pe bytes din MinIO — același algoritm ca legacy
(rotație -90°, salvare JPEG 85). Vezi `_rotate_jpeg_bytes` mai jos.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.api import APIRouter
from app.core.config import settings
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_user
from app.modules.gallery import service as gallery_svc
from app.modules.mkt_concurenta import service as svc
from app.modules.mkt_concurenta.schemas import (
    ConcurentaFolderEnsureRequest,
    ConcurentaFolderOut,
    ConcurentaMonthCell,
    ConcurentaPhotoOut,
    ConcurentaPhotosResponse,
    ConcurentaUploadResponse,
    ConcurentaYearResponse,
)
from app.modules.users.models import User

router = APIRouter(
    prefix="/api/marketing/concurenta", tags=["marketing-concurenta"]
)

# Identic cu legacy `ALLOWED_IMG_EXT` din routes/gallery.py:28
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB — conform gallery router


def _cell_to_out(cell: dict) -> ConcurentaMonthCell:
    return ConcurentaMonthCell.model_validate(cell)


def _photo_to_out(photo) -> ConcurentaPhotoOut:
    url = gallery_svc.photo_url(photo)
    return ConcurentaPhotoOut(
        id=photo.id,
        folder_id=photo.folder_id,
        filename=photo.filename,
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        caption=photo.caption,
        uploaded_at=photo.uploaded_at,
        url=url,
        thumb_url=url,  # MinIO nu generează thumb-uri; fallback la full (legacy face la fel)
    )


@router.get("", response_model=ConcurentaYearResponse)
async def list_year_grid(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConcurentaYearResponse:
    """
    Grid de 12 luni pentru un an. Port exact al blocului
    `window.loadConcurenta = async function()` din legacy (~12833).
    """
    data = await svc.list_year(session, current_user.tenant_id, year)
    return ConcurentaYearResponse(
        year=data["year"],
        cells=[_cell_to_out(c) for c in data["cells"]],
    )


@router.post(
    "/folders",
    response_model=ConcurentaFolderOut,
    status_code=status.HTTP_201_CREATED,
)
async def ensure_month_folder(
    request: Request,
    payload: ConcurentaFolderEnsureRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConcurentaFolderOut:
    """
    Creează folder `YYYY_MM` dacă nu există. Idempotent — legacy crea
    folder-ul implicit la primul upload (`os.makedirs(folder_path, exist_ok=True)`).
    """
    folder = await svc.ensure_folder(
        session, current_user.tenant_id, payload.year, payload.month
    )
    await audit_service.log_event(
        session,
        event_type="mkt_concurenta.folder.ensured",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="gallery_folder",
        target_id=folder.id,
        metadata={"year": payload.year, "month": payload.month},
        request=request,
    )
    return ConcurentaFolderOut(
        id=folder.id,
        folder_key=folder.name,
        year=payload.year,
        month=payload.month,
        created_at=folder.created_at,
    )


@router.get(
    "/months/{folder_key}/photos",
    response_model=ConcurentaPhotosResponse,
)
async def list_month_photos(
    folder_key: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConcurentaPhotosResponse:
    """
    Lista de poze pentru o lună. Dacă folder-ul nu există încă,
    returnăm 200 cu `images: []` — legacy răspundea cu text gol la 404
    și UI-ul trata ambele ca „nicio poză".
    """
    folder = await svc.get_folder_by_key(session, current_user.tenant_id, folder_key)
    if folder is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "code": "folder_not_found",
                "message": "Folderul nu exista",
            },
        )
    photos = await svc.list_photos(session, current_user.tenant_id, folder)
    return ConcurentaPhotosResponse(
        folder_key=folder.name,
        folder_id=folder.id,
        images=[_photo_to_out(p) for p in photos],
    )


@router.post(
    "/months/{folder_key}/photos",
    response_model=ConcurentaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_month_photos(
    request: Request,
    folder_key: str,
    images: list[UploadFile],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConcurentaUploadResponse:
    """
    Upload multi-file. Oglinda `window.concUpload` din legacy (~12958):
      - FormData cu `images` repetat
      - creează folder-ul dacă nu există (legacy: `os.makedirs(..., exist_ok=True)`)
      - răspunde `{uploaded, errors}`
    """
    parsed = svc._parse_folder_key(folder_key)
    if parsed is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_folder_key", "message": "Folder invalid"},
        )
    year, month = parsed
    folder = await svc.ensure_folder(session, current_user.tenant_id, year, month)

    if not images:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_files", "message": "Nu s-au selectat fisiere"},
        )

    uploaded = 0
    errors: list[str] = []
    for f in images:
        if not f.filename:
            continue
        content_type = f.content_type or "application/octet-stream"
        if content_type not in ALLOWED_CONTENT_TYPES:
            errors.append(f"{f.filename}: format nesuportat")
            continue
        content = await f.read()
        if not content:
            errors.append(f"{f.filename}: fisier gol")
            continue
        if len(content) > MAX_UPLOAD_BYTES:
            errors.append(f"{f.filename}: prea mare (>15 MB)")
            continue
        photo = await gallery_svc.upload_photo(
            session,
            tenant_id=current_user.tenant_id,
            folder=folder,
            filename=f.filename,
            content=content,
            content_type=content_type,
            uploaded_by_user_id=current_user.id,
        )
        await audit_service.log_event(
            session,
            event_type="mkt_concurenta.photo.uploaded",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            target_type="gallery_photo",
            target_id=photo.id,
            metadata={
                "folder_key": folder.name,
                "filename": photo.filename,
                "size_bytes": photo.size_bytes,
            },
            request=request,
        )
        uploaded += 1

    return ConcurentaUploadResponse(
        uploaded=uploaded, errors=errors, folder_id=folder.id
    )


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    request: Request,
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Șterge o poză. Oglinda `window.concDeleteImg` din legacy (~12977)."""
    photo = await gallery_svc.get_photo(session, current_user.tenant_id, photo_id)
    if photo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poza nu exista"},
        )
    filename = photo.filename
    folder_id = photo.folder_id
    await gallery_svc.delete_photo(session, photo)
    await audit_service.log_event(
        session,
        event_type="mkt_concurenta.photo.deleted",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="gallery_photo",
        target_id=photo_id,
        metadata={"filename": filename, "folder_id": str(folder_id)},
        request=request,
    )
    return None


def _rotate_jpeg_bytes(content: bytes) -> bytes:
    """
    Rotire 90° orar, JPEG quality 85. Port literal din legacy
    `api_gallery_rotate_image` (routes/gallery.py:410).

      img = Image.open(fpath)
      img = img.rotate(-90, expand=True)
      if img.mode != 'RGB': img = img.convert('RGB')
      img.save(fpath, 'JPEG', quality=85, optimize=True)
    """
    from PIL import Image

    src = Image.open(BytesIO(content))
    rotated = src.rotate(-90, expand=True)
    if rotated.mode != "RGB":
        rotated = rotated.convert("RGB")
    buf = BytesIO()
    rotated.save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


@router.post(
    "/photos/{photo_id}/rotate",
    response_model=ConcurentaPhotoOut,
)
async def rotate_photo(
    request: Request,
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConcurentaPhotoOut:
    """
    Roteste poza 90° orar. Port din legacy `api_gallery_rotate_image`
    (routes/gallery.py:410). În SaaS, binarul e in MinIO:
      - read  (storage.get_object)
      - rotate în memorie (PIL)
      - put_object (peste același object_key)
      - actualizează content_type/size_bytes în DB
    """
    photo = await gallery_svc.get_photo(session, current_user.tenant_id, photo_id)
    if photo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poza nu exista"},
        )

    # Download din MinIO
    try:
        resp = storage.internal_client().get_object(
            settings.minio_bucket,
            photo.object_key,
        )
        raw = resp.read()
        resp.close()
        resp.release_conn()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "storage_error", "message": f"Eroare citire: {exc}"},
        ) from exc

    try:
        rotated = _rotate_jpeg_bytes(raw)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "rotate_failed", "message": f"Rotire esuata: {exc}"},
        ) from exc

    # Salvăm înapoi (acelasi key) ca JPEG
    storage.put_object(photo.object_key, rotated, "image/jpeg")
    photo.content_type = "image/jpeg"
    photo.size_bytes = len(rotated)
    await session.commit()
    await session.refresh(photo)

    await audit_service.log_event(
        session,
        event_type="mkt_concurenta.photo.rotated",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="gallery_photo",
        target_id=photo.id,
        metadata={"filename": photo.filename},
        request=request,
    )
    return _photo_to_out(photo)
