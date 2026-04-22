"""
Gallery service. MinIO storage pentru binar, DB pentru metadata.
Object key: `{tenant_id}/{folder_id}/{uuid}_{safe_filename}`.
"""
import re
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config import settings
from app.modules.gallery.models import GalleryFolder, GalleryPhoto


def _safe_filename(name: str) -> str:
    """Înlocuiește caractere non-safe pentru object keys S3."""
    # Păstrează literele/cifrele/._- , restul înlocuim cu _
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:200]


async def list_folders(
    session: AsyncSession, tenant_id: UUID, type_: str | None = None
) -> list[tuple[GalleryFolder, int]]:
    """Returnează [(folder, photo_count), ...] sortat după nume. Numără doar pozele approved."""
    count_subq = (
        select(GalleryPhoto.folder_id, func.count(GalleryPhoto.id).label("n"))
        .where(
            GalleryPhoto.tenant_id == tenant_id,
            GalleryPhoto.approval_status == "approved",
        )
        .group_by(GalleryPhoto.folder_id)
        .subquery()
    )
    filters = [GalleryFolder.tenant_id == tenant_id]
    if type_:
        filters.append(GalleryFolder.type == type_)
    stmt = (
        select(GalleryFolder, func.coalesce(count_subq.c.n, 0))
        .outerjoin(count_subq, count_subq.c.folder_id == GalleryFolder.id)
        .where(*filters)
        .order_by(GalleryFolder.name)
    )
    result = await session.execute(stmt)
    return [(f, int(n)) for f, n in result.all()]


async def get_folder(
    session: AsyncSession, tenant_id: UUID, folder_id: UUID
) -> GalleryFolder | None:
    result = await session.execute(
        select(GalleryFolder).where(
            GalleryFolder.id == folder_id, GalleryFolder.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def create_folder(
    session: AsyncSession, *, tenant_id: UUID, type_: str, name: str
) -> GalleryFolder:
    folder = GalleryFolder(tenant_id=tenant_id, type=type_, name=name)
    session.add(folder)
    await session.commit()
    await session.refresh(folder)
    return folder


async def delete_folder(session: AsyncSession, folder: GalleryFolder) -> int:
    """Șterge folderul + toate fotografiile (DB + MinIO). Returnează count fotografii șterse."""
    photos_result = await session.execute(
        select(GalleryPhoto).where(GalleryPhoto.folder_id == folder.id)
    )
    photos = list(photos_result.scalars().all())
    for p in photos:
        try:
            storage.remove_object(p.object_key)
        except Exception:
            # Best-effort — nu blocăm ștergerea DB dacă MinIO e indisponibil
            pass
    await session.delete(folder)
    await session.commit()
    return len(photos)


async def list_photos(
    session: AsyncSession, tenant_id: UUID, folder_id: UUID,
    *, include_pending: bool = False,
) -> list[GalleryPhoto]:
    filters = [
        GalleryPhoto.tenant_id == tenant_id,
        GalleryPhoto.folder_id == folder_id,
    ]
    if not include_pending:
        filters.append(GalleryPhoto.approval_status == "approved")
    result = await session.execute(
        select(GalleryPhoto).where(*filters).order_by(GalleryPhoto.uploaded_at.desc())
    )
    return list(result.scalars().all())


async def list_pending_photos(
    session: AsyncSession, tenant_id: UUID,
) -> list[tuple[GalleryPhoto, GalleryFolder]]:
    result = await session.execute(
        select(GalleryPhoto, GalleryFolder)
        .join(GalleryFolder, GalleryFolder.id == GalleryPhoto.folder_id)
        .where(
            GalleryPhoto.tenant_id == tenant_id,
            GalleryPhoto.approval_status == "pending",
        )
        .order_by(GalleryPhoto.uploaded_at.desc())
    )
    return [(p, f) for p, f in result.all()]


async def count_pending(session: AsyncSession, tenant_id: UUID) -> int:
    result = await session.execute(
        select(func.count(GalleryPhoto.id)).where(
            GalleryPhoto.tenant_id == tenant_id,
            GalleryPhoto.approval_status == "pending",
        )
    )
    return int(result.scalar() or 0)


async def set_approval(
    session: AsyncSession, photo: GalleryPhoto,
    *, status: str, approved_by_user_id: UUID,
) -> None:
    from datetime import datetime, timezone as _tz
    if status not in ("approved", "rejected"):
        raise ValueError("status must be approved or rejected")
    photo.approval_status = status
    photo.approved_by_user_id = approved_by_user_id
    photo.approved_at = datetime.now(_tz.utc)
    await session.commit()


async def get_photo(
    session: AsyncSession, tenant_id: UUID, photo_id: UUID
) -> GalleryPhoto | None:
    result = await session.execute(
        select(GalleryPhoto).where(
            GalleryPhoto.id == photo_id, GalleryPhoto.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def upload_photo(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    folder: GalleryFolder,
    filename: str,
    content: bytes,
    content_type: str,
    uploaded_by_user_id: UUID | None = None,
    caption: str | None = None,
) -> GalleryPhoto:
    safe = _safe_filename(filename)
    object_key = f"{tenant_id}/{folder.id}/{uuid4().hex}_{safe}"
    storage.put_object(object_key, content, content_type)

    photo = GalleryPhoto(
        tenant_id=tenant_id,
        folder_id=folder.id,
        filename=filename,
        object_key=object_key,
        content_type=content_type,
        size_bytes=len(content),
        caption=caption,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def delete_photo(session: AsyncSession, photo: GalleryPhoto) -> None:
    try:
        storage.remove_object(photo.object_key)
    except Exception:
        pass
    await session.delete(photo)
    await session.commit()


def photo_url(photo: GalleryPhoto, ttl_minutes: int = 60) -> str:
    """URL proxy prin backend (evită MinIO signature mismatch în dev).
    Endpoint-ul `/api/gallery/photos/{id}/raw` streamează conținutul direct.
    """
    return f"/api/gallery/photos/{photo.id}/raw"
