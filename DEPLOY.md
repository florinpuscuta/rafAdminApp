# Deploy production

Ghid pentru deploy pe un VPS cu Docker + domeniu propriu + Let's Encrypt.

## Pre-condiții

- VPS cu Linux (Ubuntu 22.04 LTS recomandat), **minim 2GB RAM**, 2+ CPU,
  40GB disk
- Domeniu cu DNS A-record pointat la IP-ul VPS-ului (ex: `app.exemplu.ro`)
- Porturile 80 + 443 deschise în firewall (`ufw allow 80 && ufw allow 443`)
- Docker + docker-compose plugin instalate (`curl -fsSL https://get.docker.com | sh`)

## 1) Clone + env

```bash
git clone <repo-url> adeplast-saas
cd adeplast-saas
cp .env .env.prod
```

Editează `.env.prod` cu valori reale de producție:

```bash
# Bază
POSTGRES_USER=adeplast
POSTGRES_PASSWORD=<parolă-puternică-32-char>
POSTGRES_DB=adeplast_saas
DATABASE_URL=postgresql+asyncpg://adeplast:<parolă>@db:5432/adeplast_saas
APP_ENV=production

# Securitate
JWT_SECRET=<64-char-random, ex: openssl rand -hex 32>
FRONTEND_URL=https://app.exemplu.ro
# CORS — comma-separated, obligatoriu cu schemă completă (https://)
CORS_ALLOWED_ORIGINS=https://app.exemplu.ro

# Domeniu (folosit de nginx)
DOMAIN=app.exemplu.ro

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=<schimbă>
MINIO_SECRET_KEY=<schimbă, 40+ char>
MINIO_BUCKET=adeplast-saas
MINIO_PUBLIC_ENDPOINT=app.exemplu.ro  # dacă servești via nginx subpath

# SMTP (obligatoriu pt signup/invitații)
SMTP_HOST=smtp.resend.com
SMTP_PORT=465
SMTP_USER=resend
SMTP_PASSWORD=<api-key>
SMTP_FROM_EMAIL=no-reply@exemplu.ro
SMTP_FROM_NAME=Adeplast SaaS
SMTP_USE_TLS=true
SMTP_USE_STARTTLS=false

# Sentry (opțional dar recomandat)
SENTRY_DSN=https://<key>@sentry.io/<project>
SENTRY_ENVIRONMENT=production
VITE_SENTRY_DSN=https://<key>@sentry.io/<project>
VITE_SENTRY_ENVIRONMENT=production

# Version info (opțional — pt /api/version și Sentry release)
APP_VERSION=1.0.0
APP_GIT_SHA=$(git rev-parse --short HEAD)
VITE_APP_VERSION=1.0.0
```

## 2) Prim deploy — obține certificatul SSL

La prima pornire, certbot cere un challenge HTTP. Ridicăm nginx fără SSL întâi
ca să servească challenge-ul:

```bash
# Scoate temporar blocul "server { listen 443; ... }" din nginx/nginx.conf
# (sau folosește o variantă "bootstrap" — vezi nginx/nginx.bootstrap.conf
# dacă există)

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d db backend frontend nginx

# Obține certificatul
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm certbot \
  certonly --webroot -w /var/www/certbot \
  -d app.exemplu.ro \
  --email admin@exemplu.ro \
  --agree-tos --no-eff-email

# Reactivează blocul HTTPS din nginx.conf, restart nginx
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate nginx
```

După prima configurare, certbot rulează ca serviciu permanent care încearcă
renewal la fiecare 12h.

## 3) Deploy normal

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Alembic migrațiile rulează automat la start (via `docker-entrypoint.prod.sh`).

## 4) Verificare sănătate

```bash
# Health check (public, fără auth)
curl https://app.exemplu.ro/api/health | jq

# Version
curl https://app.exemplu.ro/api/version | jq

# Logs structurate JSON — util pt log aggregator (Loki, etc)
docker compose -f docker-compose.prod.yml logs -f backend
```

Răspunsul de la `/api/health` include status per componentă (db, storage, email,
sentry). HTTP 200 dacă toate sunt OK, 503 dacă vreuna a picat.

## 5) Backup DB

Un backup zilnic via cron (host), 14 zile retenție:

```bash
# /etc/cron.daily/adeplast-backup
#!/bin/bash
set -e
BACKUP_DIR=/var/backups/adeplast
mkdir -p "$BACKUP_DIR"
DATE=$(date +%Y%m%d-%H%M%S)

docker compose -f /srv/adeplast-saas/docker-compose.prod.yml \
  --env-file /srv/adeplast-saas/.env.prod \
  exec -T db pg_dump -U $POSTGRES_USER -d $POSTGRES_DB \
  | gzip > "$BACKUP_DIR/pg_$DATE.sql.gz"

# Retenție 14 zile
find "$BACKUP_DIR" -name "pg_*.sql.gz" -mtime +14 -delete
```

Chmod +x și rulează manual prima dată ca să verifici.

Pentru production real, sync periodic la S3 / Backblaze B2 / rsync.net.

## 6) Rollback

```bash
# Checkout commit anterior știut stabil
git checkout <sha-stabil>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Dacă o migrație e problematică, downgrade cu Alembic:
docker compose -f docker-compose.prod.yml exec backend \
  alembic downgrade -1
```

## Operaționalizare

- **Uptime monitoring**: UptimeRobot / Better Stack — GET `/api/health` la 1 min
- **Error tracking**: Sentry (backend + frontend, setat via env)
- **CI gate**: PR-urile sunt rulate prin GitHub Actions (pytest + vitest + docker
  build). Nu merge direct în main fără CI verde.
- **Restart automat**: toate serviciile au `restart: unless-stopped` — docker
  daemon le repornește la reboot / crash.

## Troubleshooting

| Simptom                                      | Cauză probabilă                                       |
| -------------------------------------------- | ----------------------------------------------------- |
| 502 Bad Gateway de la nginx                  | Backend pornește migrații; așteaptă 30s               |
| Login dă 500                                 | DB nu e accesibil; verifică `docker compose logs db`  |
| Emailuri de signup nu vin                    | SMTP_HOST neconfigurat → merg în log (`logs backend`) |
| `/api/health` arată `storage: fail`          | MinIO nu pornește; verifică volume permissions        |
| Sentry primește 0 events                     | `VITE_SENTRY_DSN` lipsește la build-time (rebuilt!)   |
| Browser: "blocked by CORS policy"            | `CORS_ALLOWED_ORIGINS` nu include domeniul frontend   |
