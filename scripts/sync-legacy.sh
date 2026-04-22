#!/bin/bash
# Sync periodic marketing + taskuri din PythonAnywhere (floraf2) → SaaS pe VPS.
# Rulare via cron:
#   */5 * * * * EXPORT_TOKEN=... /opt/adeplast-saas/scripts/sync-legacy.sh >> /var/log/legacy-sync.log 2>&1
set -u

PA_URL="${PA_URL:-https://floraf2.pythonanywhere.com}"
EXPORT_TOKEN="${EXPORT_TOKEN:?EXPORT_TOKEN env var must be set}"
TENANT_ID="${TENANT_ID:-e6cd4519-a2b7-448c-b488-3597a70d3bc3}"
BACKEND_CONTAINER="${BACKEND_CONTAINER:-adeplast-saas-backend-1}"
WORK_DIR="${WORK_DIR:-/var/lib/legacy-sync}"
LOCK_FILE="$WORK_DIR/.lock"

mkdir -p "$WORK_DIR"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date -Iseconds)] skip: another sync running."
  exit 0
fi

echo "[$(date -Iseconds)] === sync start ==="

# ---------- 1. Download DB-uri din PA ----------
echo "[$(date -Iseconds)] downloading dbs.zip…"
if ! curl -sf --max-time 120 -o "$WORK_DIR/dbs.zip" \
       "$PA_URL/api/admin/export-db?token=$EXPORT_TOKEN"; then
  echo "[$(date -Iseconds)] ERROR: cannot download dbs.zip"
  exit 1
fi
echo "  size: $(du -h "$WORK_DIR/dbs.zip" | cut -f1)"

rm -rf "$WORK_DIR/dbs"
mkdir -p "$WORK_DIR/dbs"
unzip -q -o "$WORK_DIR/dbs.zip" -d "$WORK_DIR/dbs"

docker cp "$WORK_DIR/dbs/adeplast_ka.db" "$BACKEND_CONTAINER:/tmp/legacy_adp_ka.db" >/dev/null
docker cp "$WORK_DIR/dbs/users.db"       "$BACKEND_CONTAINER:/tmp/legacy_users.db" >/dev/null

# ---------- 2. Rulează import-urile ----------
run_import() {
  local label="$1"
  shift
  if "$@" 2>&1 | tail -20 | sed "s/^/  [$label] /"; then
    echo "  [$label] OK"
  else
    echo "  [$label] FAILED (continue)"
  fi
}

echo "[$(date -Iseconds)] running marketing imports…"

# Panouri & Standuri (data)
run_import panouri docker exec -e "TENANT_ID=$TENANT_ID" "$BACKEND_CONTAINER" \
  python scripts/import_legacy_panouri.py /tmp/legacy_adp_ka.db

# Facing Tracker (raioane, brands, snapshots, history)
run_import facing docker exec -e "TENANT_ID=$TENANT_ID" -e "LEGACY_USERS_DB=/tmp/legacy_users.db" "$BACKEND_CONTAINER" \
  python scripts/import_legacy_facing.py

# ---------- 3. Poze — doar la fiecare oră (min=00) ----------
MIN=$((10#$(date +%M)))
if [ "$MIN" -lt 5 ]; then
  echo "[$(date -Iseconds)] hourly: downloading uploads.zip…"
  if curl -sf --max-time 600 -o "$WORK_DIR/uploads.zip" \
       "$PA_URL/api/admin/export-uploads?token=$EXPORT_TOKEN"; then
    echo "  size: $(du -h "$WORK_DIR/uploads.zip" | cut -f1)"
    rm -rf "$WORK_DIR/uploads"
    mkdir -p "$WORK_DIR/uploads"
    unzip -q -o "$WORK_DIR/uploads.zip" -d "$WORK_DIR/uploads"

    # panouri photos
    if [ -d "$WORK_DIR/uploads/sikadp/panouri" ]; then
      docker exec "$BACKEND_CONTAINER" rm -rf /tmp/pa_panouri >/dev/null 2>&1
      docker cp "$WORK_DIR/uploads/sikadp/panouri" "$BACKEND_CONTAINER:/tmp/pa_panouri" >/dev/null
      run_import panouri-photos docker exec -e "TENANT_ID=$TENANT_ID" "$BACKEND_CONTAINER" \
        python scripts/import_legacy_panouri_photos.py /tmp/pa_panouri
    fi

    # magazine photos
    if [ -d "$WORK_DIR/uploads/sikadp/magazine" ]; then
      docker exec "$BACKEND_CONTAINER" rm -rf /tmp/pa_magazine >/dev/null 2>&1
      docker cp "$WORK_DIR/uploads/sikadp/magazine" "$BACKEND_CONTAINER:/tmp/pa_magazine" >/dev/null
      run_import magazine-photos docker exec -e "TENANT_ID=$TENANT_ID" "$BACKEND_CONTAINER" \
        python scripts/import_legacy_magazine_photos.py /tmp/pa_magazine
    fi

    # concurenta photos (reuse magazine import cu type=concurenta)
    if [ -d "$WORK_DIR/uploads/sikadp/concurenta" ]; then
      docker exec "$BACKEND_CONTAINER" rm -rf /tmp/pa_concurenta >/dev/null 2>&1
      docker cp "$WORK_DIR/uploads/sikadp/concurenta" "$BACKEND_CONTAINER:/tmp/pa_concurenta" >/dev/null
      run_import concurenta-photos docker exec -e "TENANT_ID=$TENANT_ID" "$BACKEND_CONTAINER" \
        python scripts/import_legacy_magazine_photos.py /tmp/pa_concurenta concurenta
    fi

    # catalog photos
    if [ -d "$WORK_DIR/uploads/sikadp/catalog" ]; then
      docker exec "$BACKEND_CONTAINER" rm -rf /tmp/pa_catalog >/dev/null 2>&1
      docker cp "$WORK_DIR/uploads/sikadp/catalog" "$BACKEND_CONTAINER:/tmp/pa_catalog" >/dev/null
      run_import catalog-photos docker exec -e "TENANT_ID=$TENANT_ID" "$BACKEND_CONTAINER" \
        python scripts/import_legacy_catalog_photos.py /tmp/pa_catalog
    fi
  else
    echo "  uploads download failed (skip)"
  fi
fi

echo "[$(date -Iseconds)] === sync done ==="
