"""Descarcă recursiv un director de pe PythonAnywhere (legacy adeplast-dashboard)
via API public. Folosit pentru catalog, probleme, etc.

Utilizare:
    python scripts/download_pa_photos.py <remote_path> <local_dir>

Ex:
    docker exec adeplast-saas-backend-1 python scripts/download_pa_photos.py \
      /home/floraf2/adeplast-dashboard/uploads/sikadp/catalog /tmp/pa_catalog
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse as up
import urllib.request
from pathlib import Path

PA_USER = "floraf2"
PA_TOKEN = "152e9c3aec158c8335d1d41499424db931d9b251"
BASE = f"https://www.pythonanywhere.com/api/v0/user/{PA_USER}/files"
HEADERS = {"Authorization": f"Token {PA_TOKEN}"}

IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _get(url: str, timeout: int = 30) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""


def _path_url(path: str) -> str:
    # Encodăm doar spațiile, nu slash-urile (PA acceptă ambele, dar quote
    # full-path encodează și `/` ceea ce strică endpoint-ul).
    return f"{BASE}/path{path.replace(' ', '%20')}"


def list_dir(remote_path: str) -> list[str]:
    """PA API returns flat list: dirs end with `/`, files don't."""
    url = f"{BASE}/tree/?path={remote_path.replace(' ', '%20')}"
    status, body = _get(url)
    if status != 200:
        raise RuntimeError(f"tree {remote_path} → {status}")
    return json.loads(body.decode("utf-8"))


def download_file(remote_path: str, local_path: Path) -> int:
    url = _path_url(remote_path)
    status, body = _get(url, timeout=60)
    if status != 200 or not body:
        return 0
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(body)
    return len(body)


def walk(remote_root: str, local_root: Path, downloaded=None):
    """PA tree API e RECURSIV — returnează toate fișierele sub remote_root.
    Doar iterăm lista o singură dată și preservăm structura de directoare.
    """
    if downloaded is None:
        downloaded = [0, 0]
    try:
        entries = list_dir(remote_root)
    except Exception as e:
        print(f"  !! {remote_root}: {e}")
        return downloaded

    root_prefix = remote_root.rstrip("/") + "/"
    for entry in entries:
        if entry.endswith("/"):
            continue  # directoare — se pot lista separat dacă vrem, nu acum
        if not entry.startswith(root_prefix):
            continue
        rel = entry[len(root_prefix):]
        parts = rel.split("/")
        # Skip thumbnail directories (ex: "2026-03/thumbs/xxx.jpg").
        if any(p == "thumbs" for p in parts[:-1]):
            continue
        name = parts[-1]
        if Path(name).suffix.lower() not in IMG_EXTS:
            continue
        if name.startswith("thumb_"):
            continue
        local = local_root / rel
        if local.exists():
            continue
        n = download_file(entry, local)
        if n > 0:
            downloaded[0] += 1
            downloaded[1] += n
            if downloaded[0] % 10 == 0:
                print(f"  [{downloaded[0]} files, {downloaded[1] // 1024} KB]")
    return downloaded


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <remote_path> <local_dir>")
    remote = sys.argv[1]
    local = Path(sys.argv[2])
    local.mkdir(parents=True, exist_ok=True)
    print(f"[scan] {remote} → {local}")
    count, size = walk(remote, local)
    print(f"[done] {count} files, {size // 1024} KB")


if __name__ == "__main__":
    main()
