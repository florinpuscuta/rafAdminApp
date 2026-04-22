from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.gallery import service as gallery_service
from app.modules.gallery.schemas import (
    CreateFolderRequest,
    FolderOut,
    PendingPhotoOut,
    PendingSummary,
    PhotoOut,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/gallery", tags=["gallery"])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


def _photo_to_out(photo, include_url: bool = True) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        folder_id=photo.folder_id,
        filename=photo.filename,
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        caption=photo.caption,
        uploaded_by_user_id=photo.uploaded_by_user_id,
        uploaded_at=photo.uploaded_at,
        url=gallery_service.photo_url(photo) if include_url else "",
        approval_status=photo.approval_status,
    )


@router.get("/folders", response_model=list[FolderOut])
async def list_folders(
    type: str | None = Query(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    pairs = await gallery_service.list_folders(session, tenant_id, type_=type)
    return [
        FolderOut(
            id=f.id,
            type=f.type,
            name=f.name,
            created_at=f.created_at,
            photo_count=count,
        )
        for f, count in pairs
    ]


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: Request,
    payload: CreateFolderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        folder = await gallery_service.create_folder(
            session,
            tenant_id=current_user.tenant_id,
            type_=payload.type,
            name=payload.name,
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "folder_exists", "message": "Există deja un folder cu acest nume"},
        )
    await audit_service.log_event(
        session,
        event_type="gallery.folder.created",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="gallery_folder",
        target_id=folder.id,
        metadata={"type": folder.type, "name": folder.name},
        request=request,
    )
    return FolderOut(
        id=folder.id,
        type=folder.type,
        name=folder.name,
        created_at=folder.created_at,
        photo_count=0,
    )


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    request: Request,
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    folder = await gallery_service.get_folder(session, current_user.tenant_id, folder_id)
    if folder is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "folder_not_found", "message": "Folder inexistent"},
        )
    count = await gallery_service.delete_folder(session, folder)
    await audit_service.log_event(
        session,
        event_type="gallery.folder.deleted",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="gallery_folder",
        target_id=folder_id,
        metadata={"name": folder.name, "photos_deleted": count},
        request=request,
    )
    return None


@router.get("/folders/{folder_id}/photos", response_model=list[PhotoOut])
async def list_photos(
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    folder = await gallery_service.get_folder(session, current_user.tenant_id, folder_id)
    if folder is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "folder_not_found", "message": "Folder inexistent"},
        )
    photos = await gallery_service.list_photos(
        session, current_user.tenant_id, folder_id
    )
    return [_photo_to_out(p) for p in photos]


@router.post(
    "/folders/{folder_id}/photos",
    response_model=PhotoOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    request: Request,
    folder_id: UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    folder = await gallery_service.get_folder(session, current_user.tenant_id, folder_id)
    if folder is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "folder_not_found", "message": "Folder inexistent"},
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

    photo = await gallery_service.upload_photo(
        session,
        tenant_id=current_user.tenant_id,
        folder=folder,
        filename=file.filename or "untitled",
        content=content,
        content_type=content_type,
        uploaded_by_user_id=current_user.id,
    )
    await audit_service.log_event(
        session,
        event_type="gallery.photo.uploaded",
        tenant_id=current_user.tenant_id,
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
    return _photo_to_out(photo)


@router.post("/photos/{photo_id}/rotate")
async def rotate_photo(
    photo_id: UUID,
    direction: str = "right",  # "left" | "right"
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Rotește poza 90° (stânga sau dreapta). Port din legacy
    `concRotateImg`. Modifică binarul MinIO in-place.
    """
    from io import BytesIO
    from PIL import Image, ImageOps
    from app.core import storage
    photo = await gallery_service.get_photo(session, current_user.tenant_id, photo_id)
    if photo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poză inexistentă"},
        )
    data, content_type = storage.get_object_stream(photo.object_key)
    try:
        img = Image.open(BytesIO(data))
        img = ImageOps.exif_transpose(img)
        angle = -90 if direction == "right" else 90
        rotated = img.rotate(angle, expand=True)
        out = BytesIO()
        fmt = (photo.content_type or content_type or "image/jpeg").split("/")[-1].upper()
        if fmt == "JPG":
            fmt = "JPEG"
        if fmt not in {"JPEG", "PNG", "GIF", "WEBP"}:
            fmt = "JPEG"
        if fmt == "JPEG" and rotated.mode != "RGB":
            rotated = rotated.convert("RGB")
        rotated.save(out, format=fmt, quality=92)
        storage.put_object(
            photo.object_key, out.getvalue(),
            photo.content_type or f"image/{fmt.lower()}",
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rotire eșuată: {e}",
        )
    return {"ok": True}


@router.get("/photos/{photo_id}/raw")
async def get_photo_raw(
    photo_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Stream conținutul fotografiei prin backend (proxy MinIO). Public read
    (UUID-ul e protecția — nu e enumerabil). Folosit de tag-uri <img src=...>
    care nu pot trimite bearer token în header.
    """
    from fastapi.responses import Response
    from sqlalchemy import select as _sel
    from app.core import storage
    from app.modules.gallery.models import GalleryPhoto
    photo = (await session.execute(
        _sel(GalleryPhoto).where(GalleryPhoto.id == photo_id)
    )).scalar_one_or_none()
    if photo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poză inexistentă"},
        )
    data, content_type = storage.get_object_stream(photo.object_key)
    return Response(
        content=data,
        media_type=photo.content_type or content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    request: Request,
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    photo = await gallery_service.get_photo(session, current_user.tenant_id, photo_id)
    if photo is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "photo_not_found", "message": "Poză inexistentă"},
        )
    filename = photo.filename
    await gallery_service.delete_photo(session, photo)
    await audit_service.log_event(
        session,
        event_type="gallery.photo.deleted",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="gallery_photo",
        target_id=photo_id,
        metadata={"filename": filename},
        request=request,
    )
    return None


# ─── Approval workflow ─────────────────────────────────────────────────────

@router.get("/pending/summary", response_model=PendingSummary)
async def pending_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    count = await gallery_service.count_pending(session, current_user.tenant_id)
    return PendingSummary(pending_count=count)


@router.get("/pending", response_model=list[PendingPhotoOut])
async def list_pending(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "forbidden", "message": "Doar admin poate vedea pozele de aprobat",
        })
    pairs = await gallery_service.list_pending_photos(session, current_user.tenant_id)
    return [
        PendingPhotoOut(
            id=p.id, folder_id=p.folder_id, filename=p.filename,
            content_type=p.content_type, size_bytes=p.size_bytes,
            caption=p.caption, uploaded_by_user_id=p.uploaded_by_user_id,
            uploaded_at=p.uploaded_at,
            url=gallery_service.photo_url(p),
            approval_status=p.approval_status,
            folder_type=f.type, folder_name=f.name,
        )
        for p, f in pairs
    ]


@router.post("/photos/{photo_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_photo(
    request: Request, photo_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "forbidden", "message": "Doar admin poate aproba",
        })
    photo = await gallery_service.get_photo(session, current_user.tenant_id, photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "photo_not_found", "message": "Poză inexistentă",
        })
    await gallery_service.set_approval(
        session, photo, status="approved", approved_by_user_id=current_user.id,
    )
    await audit_service.log_event(
        session, event_type="gallery.photo.approved",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        target_type="gallery_photo", target_id=photo_id,
        metadata={"filename": photo.filename}, request=request,
    )
    return None


@router.post("/photos/{photo_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_photo(
    request: Request, photo_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "forbidden", "message": "Doar admin poate respinge",
        })
    photo = await gallery_service.get_photo(session, current_user.tenant_id, photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "photo_not_found", "message": "Poză inexistentă",
        })
    filename = photo.filename
    await gallery_service.delete_photo(session, photo)
    await audit_service.log_event(
        session, event_type="gallery.photo.rejected",
        tenant_id=current_user.tenant_id, user_id=current_user.id,
        target_type="gallery_photo", target_id=photo_id,
        metadata={"filename": filename}, request=request,
    )
    return None
