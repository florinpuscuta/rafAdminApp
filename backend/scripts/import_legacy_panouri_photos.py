"""Import fotografii legacy Panouri din uploads/sikadp/panouri/{store}/*.jpg.

Pentru fiecare folder-magazin:
  1. Creează/găsește GalleryFolder (type='panouri', name=store_name)
  2. Pentru fiecare fișier (exclude thumb_*) — upload la MinIO + creează GalleryPhoto

Rulare:
  docker cp ../adeplast-dashboard/uploads/sikadp/panouri adeplast-saas-backend-1:/tmp/pa_panouri
  docker exec adeplast-saas-backend-1 python scripts/import_legacy_panouri_photos.py /tmp/pa_panouri
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from pathlib import Path

import asyncpg

TENANT_ID = os.environ.get("TENANT_ID", "e6cd4519-a2b7-448c-b488-3597a70d3bc3")
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/pa_panouri")


def _pg_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


def _guess_content_type(fname: str) -> str:
    ext = fname.lower().rsplit(".", 1)[-1]
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


async def main():
    if not SRC.exists():
        sys.exit(f"Source dir not found: {SRC}")

    # Import MinIO client (disponibil în container backend)
    sys.path.insert(0, "/app")
    from app.core import storage

    conn = await asyncpg.connect(_pg_dsn())
    try:
        stores = sorted([d.name for d in SRC.iterdir() if d.is_dir()])
        print(f"[scan] {len(stores)} store folders")

        total_up, total_skip, total_fail = 0, 0, 0
        for i, store in enumerate(stores, 1):
            store_dir = SRC / store
            files = [
                f for f in sorted(store_dir.iterdir())
                if f.is_file()
                and not f.name.startswith("thumb_")
                and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            ]
            if not files:
                continue

            # Upsert GalleryFolder
            folder_id = await conn.fetchval(
                """INSERT INTO gallery_folders (id, tenant_id, type, name)
                   VALUES ($1::uuid, $2::uuid, 'panouri', $3)
                   ON CONFLICT (tenant_id, type, name)
                   DO UPDATE SET name=EXCLUDED.name
                   RETURNING id""",
                str(uuid.uuid4()), TENANT_ID, store,
            )

            for f in files:
                existing = await conn.fetchrow(
                    """SELECT id, object_key FROM gallery_photos
                       WHERE tenant_id=$1::uuid AND folder_id=$2::uuid AND filename=$3""",
                    TENANT_ID, str(folder_id), f.name,
                )
                if existing:
                    try:
                        storage.get_object_stream(existing["object_key"])
                        total_skip += 1
                        continue
                    except Exception:
                        try:
                            storage.put_object(
                                existing["object_key"], f.read_bytes(),
                                _guess_content_type(f.name),
                            )
                            total_up += 1
                        except Exception as e:
                            total_fail += 1
                            print(f"  !! reupload {store}/{f.name}: {e}")
                        continue
                try:
                    data = f.read_bytes()
                    safe = re.sub(r"[^\w.\-]+", "_", f.name)
                    object_key = f"{TENANT_ID}/{folder_id}/{uuid.uuid4().hex}_{safe}"
                    ctype = _guess_content_type(f.name)
                    storage.put_object(object_key, data, ctype)
                    await conn.execute(
                        """INSERT INTO gallery_photos
                           (id, tenant_id, folder_id, filename, object_key,
                            content_type, size_bytes, approval_status)
                           VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, 'pending')""",
                        str(uuid.uuid4()), TENANT_ID, str(folder_id),
                        f.name, object_key, ctype, len(data),
                    )
                    total_up += 1
                except Exception as e:
                    total_fail += 1
                    print(f"  !! FAIL {store}/{f.name}: {e}")

            if i % 10 == 0 or i == len(stores):
                print(f"  [{i}/{len(stores)}] stores · up={total_up} skip={total_skip} fail={total_fail}")

        print(f"\n[done] uploaded={total_up}, skipped={total_skip}, failed={total_fail}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
