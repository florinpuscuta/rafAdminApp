# Backup & Restore — Adeplast SaaS

Ghid pentru backup automat zilnic al DB Postgres + uploads (MinIO) către
S3 extern (Hetzner Object Storage), retention pe 3 niveluri și procedură
de restore.

---

## 1. De ce S3 extern

Hetzner Snapshots (snapshot-ul VPS-ului întreg) e singurul backup actual.
Limite:
- nu e granular (nu poți restaura *doar DB*-ul);
- e legat de același cont Hetzner (single point of failure);
- nu acoperă cazul "Florin a șters din greșeală un client".

Soluția: **dump zilnic SQL + sync MinIO uploads** către un bucket S3
**separat de instanța VPS** (ideal alt provider, sau cel puțin alt cont
Hetzner). Retention: 7 zilnice + 4 săptămânale + 6 lunare. Restaurare
testată cu script dedicat.

---

## 2. Provisioning Hetzner Object Storage (one-time, ~10 min)

1. Hetzner Cloud Console → **Object Storage** → **New Bucket**.
   - Nume: `adeplast-backups` (sau ce vrei).
   - Locație: alegere alta decât VPS-ul (ex: VPS în `nbg1-dc3` → bucket
     în `fsn1` — Falkenstein, pentru izolare fizică).
2. Hetzner → **Security → S3 Credentials → Generate**.
   Notează `ACCESS_KEY` + `SECRET_KEY`.
3. **Endpoint** standard Hetzner: `https://{REGION}.your-objectstorage.com`
   (ex: `https://fsn1.your-objectstorage.com`).

Alternativă: AWS S3, Backblaze B2, Cloudflare R2. Toate compatibile S3.

---

## 3. Setup pe server (one-time)

Pe `178.104.82.60`:

```bash
# 1. Instalează rclone
curl https://rclone.org/install.sh | sudo bash

# 2. Configurează remote-ul "s3backup"
rclone config
# Răspunsuri:
#   n (new remote)
#   name: s3backup
#   storage: 5 (Amazon S3 Compliant)
#   provider: 19 (Other / Hetzner)
#   env_auth: 1 (false)
#   access_key_id: <din Hetzner>
#   secret_access_key: <din Hetzner>
#   region: <gol pentru Hetzner>
#   endpoint: https://fsn1.your-objectstorage.com
#   location_constraint: <gol>
#   acl: private
#   server_side_encryption: <gol>
#   storage_class: <gol>
#   advanced: n
#   y (yes, this is OK)

# 3. Test
rclone mkdir s3backup:adeplast-backups
rclone ls s3backup:adeplast-backups       # ar trebui gol

# 4. Configurează variabilele de backup
cat > /opt/adeplast-saas/.env.backup <<EOF
S3_REMOTE=s3backup
S3_BUCKET=adeplast-backups
BACKUP_PREFIX=prod
RETENTION_DAYS=7
RETENTION_WEEKS=4
RETENTION_MONTHS=6
# SENTRY_DSN=https://...   # opțional, alerte la eșec
EOF
chmod 600 /opt/adeplast-saas/.env.backup

# 5. Test manual al script-ului
chmod +x /opt/adeplast-saas/scripts/backup.sh
/opt/adeplast-saas/scripts/backup.sh
# Verifică în Hetzner Console → bucket → vezi `prod/db/daily/...`

# 6. Cron — zilnic la 03:00 UTC
sudo crontab -e
# Adaugă linia:
0 3 * * *  /opt/adeplast-saas/scripts/backup.sh >> /var/log/adeplast-backup.log 2>&1

# 7. Verifică logul după prima rulare
tail -50 /var/log/adeplast-backup.log
```

---

## 4. Cum funcționează scriptul

`scripts/backup.sh` la fiecare rulare:

1. **`pg_dump`** prin `docker exec` pe `adeplast-saas-db-1` →
   `/var/lib/adeplast-backup/db-{ts}.sql.gz` (gzip nivel 9).
2. **`rclone copyto`** dump-ul la
   `s3backup:adeplast-backups/prod/db/{class}/db-{ts}.sql.gz`.
3. **`rclone sync`** directorul mount al MinIO către
   `s3backup:adeplast-backups/prod/uploads/{class}/{ts}/`.
4. **Retention** — șterge dump-uri / dir-uri uploads peste limita pe clasă
   (`daily`/`weekly`/`monthly`).
5. Scrie `last_success.txt` cu timestamp.

**Clase de backup:**

| Clasă     | Trigger              | Reținute |
| --------- | -------------------- | -------- |
| `daily`   | Orice rulare (default) | 7        |
| `weekly`  | Duminica (UTC)       | 4        |
| `monthly` | Prima zi a lunii (UTC) | 6        |

Aceeași dump fizică e stocată într-o singură clasă (cea mai înaltă
care match-uie). Nu duplicăm date.

---

## 5. Restore

### Restore DB

```bash
cd /opt/adeplast-saas
./scripts/restore.sh           # listează ultimele 20 daily, întreabă
./scripts/restore.sh latest    # ia ultimul success
./scripts/restore.sh db-2026-04-26T03-00-00Z.sql.gz  # nume direct
```

Scriptul:
1. Descarcă dump-ul din S3.
2. **Creează un DB temporar** (`adeplast_saas_restore_<ts>`) și încarcă
   dump-ul acolo. Niciodată nu loadăm direct peste DB-ul live.
3. **Confirmare obligatorie** ("yes") înainte să facă swap.
4. Swap (rename) DB-ul vechi la `adeplast_saas_old_<ts>`, noul devine
   `adeplast_saas`.
5. Backend-ul trebuie restartat: `docker compose -f
   /opt/adeplast-saas/docker-compose.prod.yml restart backend`.

DB-ul vechi e păstrat — îl ștergi manual cu:
```bash
docker exec -e PGPASSWORD=$POSTGRES_PASSWORD adeplast-saas-db-1 \
    psql -U postgres -d postgres -c 'DROP DATABASE "adeplast_saas_old_<ts>"'
```

### Restore uploads (MinIO)

Manual (uploads sunt rare modificate accidental):

```bash
# 1. Identifică timestamp-ul backup-ului dorit
rclone lsd s3backup:adeplast-backups/prod/uploads/daily/

# 2. Sync înapoi în volumul MinIO
docker stop adeplast-saas-minio-1
MINIO_VOL=$(docker inspect -f '{{ range .Mounts }}{{ if eq .Destination "/data" }}{{ .Source }}{{ end }}{{ end }}' adeplast-saas-minio-1)
rclone sync s3backup:adeplast-backups/prod/uploads/daily/<TS>/ "$MINIO_VOL/adeplast-saas"
docker start adeplast-saas-minio-1
```

---

## 6. Verificare backup recent

```bash
# Cel mai recent timestamp
rclone cat s3backup:adeplast-backups/prod/last_success.txt

# Listare backup-uri pe clasă
rclone lsf s3backup:adeplast-backups/prod/db/daily/   --files-only | sort -r | head
rclone lsf s3backup:adeplast-backups/prod/db/weekly/  --files-only | sort -r | head
rclone lsf s3backup:adeplast-backups/prod/db/monthly/ --files-only | sort -r | head

# Dimensiuni
rclone size s3backup:adeplast-backups/prod/
```

Recomandare: alarmă externă (UptimeRobot keyword check pe
`last_success.txt`, sau Sentry cron monitor) care urlă dacă timestamp-ul
e mai vechi de 26h.

---

## 7. Drill — restore quarterly

La fiecare 3 luni, pentru a verifica backup-urile sunt valide:

1. Ridică un VPS de test (sau un docker compose local).
2. Rulează `restore.sh` cu un dump de săptămâna trecută.
3. Verifică `/api/health` + login + un raport reprezentativ
   (ex: Consolidat KA ar trebui să arate aceleași totaluri ca pe prod).
4. Notează în `BACKUP_DRILLS.md` (TBD) data + rezultatul.

Backup-urile NEtestate **nu sunt** backup-uri.

---

## 8. Costuri estimate

Hetzner Object Storage la 2026-04-26:
- 1 TB: ~ €5.99 / lună
- Egress: gratuit între Hetzner Cloud servers; ~€1/TB către internet.

Per cont real: DB ~ 700 MB gzipped × 7 + 4 + 6 = ~12 GB. Uploads ~ 2-5 GB.
Total ~ 20 GB → cost neglijabil (€0.12/lună).

---

## 9. Roadmap (improvements)

- **Encryption GPG** la upload (asymmetric — privat offline). Pentru când
  business-ul cere izolarea backup-urilor de Hetzner ca provider.
- **Endpoint `/api/admin/backup-status`** care citește
  `last_success.txt` și expune fresh-ness pentru UI.
- **PITR** (point-in-time recovery) cu WAL-G + S3 — dacă RPO < 24h.

---

**Versiune**: 1.0 (2026-04-26)
**Owner**: Florin Pușcuța
