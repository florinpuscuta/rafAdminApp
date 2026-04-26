#!/bin/bash
# Backup zilnic: pg_dump + MinIO uploads → S3 extern (Hetzner Object Storage).
#
# Pre-condiții pe server:
#   - rclone instalat și configurat cu un remote `s3backup`
#     (vezi docs/BACKUP.md pentru config exact)
#   - container `adeplast-saas-db-1` rulează (folosit pt pg_dump)
#   - container `adeplast-saas-minio-1` rulează (folosit pt sync uploads)
#
# Crontab:
#   0 3 * * *  /opt/adeplast-saas/scripts/backup.sh >> /var/log/adeplast-backup.log 2>&1
#
# Variabile env (poți pune într-un `.env.backup` în /opt/adeplast-saas):
#   POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
#   S3_REMOTE          — numele remote-ului rclone (default "s3backup")
#   S3_BUCKET          — bucket destinație (default "adeplast-backups")
#   BACKUP_PREFIX      — prefix în bucket (default "prod")
#   RETENTION_DAYS     — zile cu backup zilnic (default 7)
#   RETENTION_WEEKS    — săptămâni cu backup săptămânal (default 4)
#   RETENTION_MONTHS   — luni cu backup lunar (default 6)
#   SENTRY_DSN         — opțional, pentru alerte la eșec
#
# Folosire manuală: `./backup.sh` (rulează la fel ca în cron).

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

# Încărcăm .env.backup dacă există
if [ -f "$DEPLOY_DIR/.env.backup" ]; then
    set -a; source "$DEPLOY_DIR/.env.backup"; set +a
fi
# Fallback la .env.prod pentru POSTGRES_*
if [ -f "$DEPLOY_DIR/.env.prod" ]; then
    set -a; source "$DEPLOY_DIR/.env.prod"; set +a
fi

S3_REMOTE="${S3_REMOTE:-s3backup}"
S3_BUCKET="${S3_BUCKET:-adeplast-backups}"
BACKUP_PREFIX="${BACKUP_PREFIX:-prod}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
RETENTION_WEEKS="${RETENTION_WEEKS:-4}"
RETENTION_MONTHS="${RETENTION_MONTHS:-6}"

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-adeplast_saas}"

DB_CONTAINER="${DB_CONTAINER:-adeplast-saas-db-1}"
MINIO_BUCKET="${MINIO_BUCKET:-adeplast-saas}"
MINIO_ENDPOINT_INTERNAL="http://localhost:9000"

WORK_DIR="${WORK_DIR:-/var/lib/adeplast-backup}"
mkdir -p "$WORK_DIR"

# Timestamp & marker pentru retention class.
NOW="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
DOW="$(date -u +%u)"        # 1=Mon..7=Sun
DOM="$(date -u +%d)"        # 01..31
CLASS="daily"
[ "$DOW" = "7" ] && CLASS="weekly"
[ "$DOM" = "01" ] && CLASS="monthly"

DUMP_FILE="$WORK_DIR/db-${NOW}.sql.gz"

# ── Logging ───────────────────────────────────────────────────────────────
log() {
    echo "[$(date -Iseconds)] $*"
}

fail() {
    log "ERROR: $*"
    if [ -n "${SENTRY_DSN:-}" ]; then
        # Trimite mesaj minim la Sentry (opțional, fail-soft).
        curl -sS -X POST "$SENTRY_DSN/store/" \
            -H "Content-Type: application/json" \
            -d "{\"message\":\"adeplast-backup failed: $*\",\"level\":\"error\",\"environment\":\"prod\"}" \
            >/dev/null 2>&1 || true
    fi
    exit 1
}

trap 'fail "script exited unexpectedly at line $LINENO"' ERR

# ── 1. pg_dump ────────────────────────────────────────────────────────────
log "=== backup start (class=$CLASS, ts=$NOW) ==="

log "running pg_dump..."
if ! docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "$DB_CONTAINER" \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain --no-owner \
    | gzip -9 > "$DUMP_FILE"; then
    fail "pg_dump failed"
fi
DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
log "  dump: $DUMP_FILE ($DUMP_SIZE)"

# ── 2. Upload DB dump la S3 ───────────────────────────────────────────────
S3_DB_PATH="${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/${CLASS}/db-${NOW}.sql.gz"
log "uploading dump to ${S3_DB_PATH}..."
if ! rclone copyto "$DUMP_FILE" "$S3_DB_PATH" --s3-no-check-bucket; then
    fail "rclone upload (db) failed"
fi

# ── 3. Sync uploads (MinIO bucket) ────────────────────────────────────────
S3_UPLOADS_PATH="${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/uploads/${CLASS}/${NOW}/"
log "syncing MinIO bucket '${MINIO_BUCKET}' to ${S3_UPLOADS_PATH}..."
# Folosim rclone direct pe path-ul Docker volume al MinIO
# (evităm overhead-ul de a expune MinIO ca remote separat).
MINIO_VOLUME="$(docker inspect -f '{{ range .Mounts }}{{ if eq .Destination "/data" }}{{ .Source }}{{ end }}{{ end }}' adeplast-saas-minio-1 2>/dev/null || echo "")"
if [ -z "$MINIO_VOLUME" ]; then
    log "WARNING: cannot find MinIO volume mount — skip uploads sync"
else
    if [ -d "$MINIO_VOLUME/$MINIO_BUCKET" ]; then
        if ! rclone sync "$MINIO_VOLUME/$MINIO_BUCKET" "$S3_UPLOADS_PATH" \
            --s3-no-check-bucket --transfers=4; then
            log "WARNING: rclone uploads sync failed (continue)"
        fi
    else
        log "  no MinIO bucket dir at $MINIO_VOLUME/$MINIO_BUCKET — skip"
    fi
fi

# ── 4. Retention — șterge backup-uri vechi pe clasă ──────────────────────
prune_class() {
    local cls="$1"
    local keep="$2"
    log "pruning ${cls} backups, keeping last ${keep}..."
    # Listăm dump-urile pe clasă, sortate desc, sărim peste primele `keep`,
    # restul le ștergem.
    rclone lsf "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/${cls}/" --files-only 2>/dev/null \
        | sort -r | tail -n +$((keep + 1)) | while read -r f; do
        log "  removing db/${cls}/${f}"
        rclone deletefile "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/${cls}/${f}" || true
    done
    # Pentru uploads e un dir per timestamp — folosim purge pe path-ul de timestamp.
    rclone lsf "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/uploads/${cls}/" --dirs-only 2>/dev/null \
        | sort -r | tail -n +$((keep + 1)) | while read -r d; do
        log "  removing uploads/${cls}/${d}"
        rclone purge "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/uploads/${cls}/${d}" || true
    done
}

prune_class daily "$RETENTION_DAYS"
prune_class weekly "$RETENTION_WEEKS"
prune_class monthly "$RETENTION_MONTHS"

# ── 5. Cleanup local ──────────────────────────────────────────────────────
rm -f "$DUMP_FILE"

# ── 6. Healthcheck — scriem un marker cu timestamp ultim backup ──────────
echo "$NOW" | rclone rcat "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/last_success.txt" \
    --s3-no-check-bucket 2>/dev/null || true

log "=== backup done ==="
