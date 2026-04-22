"""Import poze magazine din uploads/sikadp/magazine/{folder}/*.jpg în
tabela gallery (type='magazine'). Analog import_legacy_panouri_photos.
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
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/pa_magazine")
GALLERY_TYPE = sys.argv[2] if len(sys.argv) > 2 else "magazine"


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
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }.get(ext, "application/octet-stream")


async def main():
    if not SRC.exists():
        sys.exit(f"Source dir not found: {SRC}")
    sys.path.insert(0, "/app")
    from app.core import storage

    conn = await asyncpg.connect(_pg_dsn())
    try:
        # Colectează TOATE folderele care conțin fișiere imagine (recursiv).
        # Legacy may have nested `magazine/magazine/{folder}/*` sau alte niveluri.
        candidate_dirs: dict[str, Path] = {}
        for root, dirs, fnames in os.walk(SRC):
            imgs = [
                fn for fn in fnames
                if not fn.startswith("thumb_")
                and fn.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
            ]
            if imgs:
                p = Path(root)
                # Folosim numele folderului direct care conține pozele
                # (ignoră orice nivel intermediar duplicat "magazine").
                candidate_dirs[p.name] = p
        folders_sorted = sorted(candidate_dirs.keys())
        print(f"[scan] {len(folders_sorted)} folders cu poze (recursiv)")

        total_up, total_skip, total_fail = 0, 0, 0
        for i, folder_name in enumerate(folders_sorted, 1):
            folder_dir = candidate_dirs[folder_name]
            files = [
                folder_dir / fn for fn in sorted(os.listdir(folder_dir))
                if not fn.startswith("thumb_")
                and fn.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                and (folder_dir / fn).is_file()
            ]
            if not files:
                continue

            folder_id = await conn.fetchval(
                """INSERT INTO gallery_folders (id, tenant_id, type, name)
                   VALUES ($1::uuid, $2::uuid, $3, $4)
                   ON CONFLICT (tenant_id, type, name)
                   DO UPDATE SET name=EXCLUDED.name
                   RETURNING id""",
                str(uuid.uuid4()), TENANT_ID, GALLERY_TYPE, folder_name,
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
                            print(f"  !! reupload {folder_name}/{f.name}: {e}")
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
                    print(f"  !! {folder_name}/{f.name}: {e}")

            if i % 10 == 0 or i == len(folders_sorted):
                print(f"  [{i}/{len(folders_sorted)}] up={total_up} skip={total_skip} fail={total_fail}")

        print(f"\n[done] uploaded={total_up}, skipped={total_skip}, failed={total_fail}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
