"""
Object storage wrapper (MinIO / S3 compatible).

Două clienti separați:
- `internal_client` — foloseste endpoint-ul din rețeaua Docker (minio:9000);
  pentru upload/delete/exists de pe server.
- `public_client` — foloseste endpoint-ul vizibil din browser (localhost:9000);
  folosit DOAR pentru a genera presigned URLs pe care clientul le poate accesa.

La prima folosire, bucketul e creat automat dacă nu există.
"""
from datetime import timedelta

from minio import Minio

from app.core.config import settings

_internal: Minio | None = None
_public: Minio | None = None
_bucket_ensured = False


def internal_client() -> Minio:
    global _internal
    if _internal is None:
        _internal = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _internal


def public_client() -> Minio:
    global _public
    if _public is None:
        _public = Minio(
            settings.minio_public_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _public


def ensure_bucket() -> None:
    global _bucket_ensured
    if _bucket_ensured:
        return
    c = internal_client()
    if not c.bucket_exists(settings.minio_bucket):
        c.make_bucket(settings.minio_bucket)
    _bucket_ensured = True


def put_object(object_key: str, data: bytes, content_type: str) -> None:
    ensure_bucket()
    from io import BytesIO

    internal_client().put_object(
        settings.minio_bucket,
        object_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def remove_object(object_key: str) -> None:
    internal_client().remove_object(settings.minio_bucket, object_key)


def get_object_bytes(object_key: str) -> bytes:
    """Descarcă un obiect complet în memorie. Folosit pentru manipulări
    server-side (ex: rotate photo). Pentru volume mari, folosește streaming."""
    ensure_bucket()
    resp = internal_client().get_object(settings.minio_bucket, object_key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def presigned_get_url(object_key: str, expires_minutes: int = 60) -> str:
    """Presigned URL — funcționează doar dacă MINIO_PUBLIC_ENDPOINT=MINIO_ENDPOINT
    (ex. în producție cu același domeniu). Pentru dev folosim proxy-ul
    `/api/gallery/photos/{id}/raw` care evită problema signature mismatch."""
    raw = internal_client().presigned_get_object(
        settings.minio_bucket, object_key,
        expires=timedelta(minutes=expires_minutes),
    )
    internal = settings.minio_endpoint
    public = settings.minio_public_endpoint
    if internal != public:
        raw = raw.replace(f"://{internal}/", f"://{public}/", 1)
    return raw


def get_object_stream(object_key: str):
    """Returnează (data_bytes, content_type) pentru streaming prin backend."""
    ensure_bucket()
    resp = internal_client().get_object(settings.minio_bucket, object_key)
    try:
        return resp.read(), resp.headers.get("Content-Type", "application/octet-stream")
    finally:
        resp.close()
        resp.release_conn()
