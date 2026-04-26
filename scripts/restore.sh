#!/bin/bash
# Restore din backup S3 — interactiv. Listează backup-urile disponibile,
# întreabă utilizatorul, descarcă și aplică pe DB-ul live.
#
# Folosire:
#   ./restore.sh                # listează ultimele 20 dump-uri și întreabă
#   ./restore.sh <date>         # descarcă direct ex: 2026-04-26T03-00-00Z
#   ./restore.sh latest         # ia ultimul success
#
# Asumă: rclone configurat (același remote ca backup.sh), DB rulează în
# `adeplast-saas-db-1`. NU restaurează MinIO — pentru asta vezi
# `docs/BACKUP.md` § Restore uploads.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"

[ -f "$DEPLOY_DIR/.env.backup" ] && set -a && source "$DEPLOY_DIR/.env.backup" && set +a
[ -f "$DEPLOY_DIR/.env.prod" ] && set -a && source "$DEPLOY_DIR/.env.prod" && set +a

S3_REMOTE="${S3_REMOTE:-s3backup}"
S3_BUCKET="${S3_BUCKET:-adeplast-backups}"
BACKUP_PREFIX="${BACKUP_PREFIX:-prod}"
DB_CONTAINER="${DB_CONTAINER:-adeplast-saas-db-1}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-adeplast_saas}"

log() { echo "[$(date -Iseconds)] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

CHOICE="${1:-}"

if [ -z "$CHOICE" ]; then
    log "Last 20 daily backups:"
    rclone lsf "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/daily/" --files-only \
        | sort -r | head -20 | nl
    echo
    read -rp "Numărul backup-ului (1-20) sau 'latest': " choice
    if [ "$choice" = "latest" ]; then
        CHOICE="latest"
    else
        CHOICE="$(rclone lsf "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/daily/" --files-only \
            | sort -r | sed -n "${choice}p")"
    fi
fi

if [ "$CHOICE" = "latest" ]; then
    LATEST_TS="$(rclone cat "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/last_success.txt" 2>/dev/null || true)"
    [ -z "$LATEST_TS" ] && fail "no last_success.txt — nu pot determina latest"
    REMOTE_FILE="${BACKUP_PREFIX}/db/daily/db-${LATEST_TS}.sql.gz"
    # Latest poate fi în weekly sau monthly în funcție de când a rulat ultima oară
    for cls in daily weekly monthly; do
        if rclone lsf "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/${cls}/" --files-only 2>/dev/null \
            | grep -q "db-${LATEST_TS}.sql.gz"; then
            REMOTE_FILE="${BACKUP_PREFIX}/db/${cls}/db-${LATEST_TS}.sql.gz"
            break
        fi
    done
else
    # CHOICE e un nume de fișier: caută în toate clasele
    REMOTE_FILE=""
    for cls in daily weekly monthly; do
        if rclone lsf "${S3_REMOTE}:${S3_BUCKET}/${BACKUP_PREFIX}/db/${cls}/" --files-only 2>/dev/null \
            | grep -q "^${CHOICE}$"; then
            REMOTE_FILE="${BACKUP_PREFIX}/db/${cls}/${CHOICE}"
            break
        fi
    done
    [ -z "$REMOTE_FILE" ] && fail "nu găsesc fișierul $CHOICE în db/{daily,weekly,monthly}"
fi

log "Restoring from: $REMOTE_FILE"
log "Target DB: ${POSTGRES_DB} (container ${DB_CONTAINER})"
read -rp "ESTE IREVERSIBIL. Confirmă cu 'yes' ca să continui: " confirm
[ "$confirm" = "yes" ] || fail "abandonat"

LOCAL_FILE="/tmp/restore-$(date +%s).sql.gz"
rclone copyto "${S3_REMOTE}:${S3_BUCKET}/${REMOTE_FILE}" "$LOCAL_FILE"
log "  downloaded: $(du -h "$LOCAL_FILE" | cut -f1)"

# Restaurăm într-un DB temporar pentru siguranță, apoi swap-uim numele.
TMP_DB="${POSTGRES_DB}_restore_$(date +%s)"
log "creating temp DB: $TMP_DB"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CONTAINER" \
    psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$TMP_DB\""

log "loading dump..."
gunzip -c "$LOCAL_FILE" | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$TMP_DB"

log "swapping ${POSTGRES_DB} <-> ${TMP_DB}..."
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d postgres <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${POSTGRES_DB}' AND pid<>pg_backend_pid();
ALTER DATABASE "${POSTGRES_DB}" RENAME TO "${POSTGRES_DB}_old_$(date +%s)";
ALTER DATABASE "${TMP_DB}" RENAME TO "${POSTGRES_DB}";
SQL

rm -f "$LOCAL_FILE"

log "DONE. Backend trebuie restartat: docker compose -f /opt/adeplast-saas/docker-compose.prod.yml restart backend"
log "DB-ul vechi e păstrat ca ${POSTGRES_DB}_old_<ts> — șterge manual când ești confortabil."
