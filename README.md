# Adeplast SaaS

Multi-tenant SaaS pentru analiza vânzărilor Key Accounts (Adeplast, Sika).
Rewrite complet de la zero al `adeplast-dashboard` — **modular monolith +
DDD-lite** cu DB normalizată, contracte API strong-typed, migrații versionate și
separare strictă UI / backend / DB.

## Stack

**Backend** — Python 3.11, FastAPI, SQLAlchemy 2.0 async, asyncpg, Postgres 16,
Alembic, Pydantic v2 (camelCase contracts), slowapi (rate limit), MinIO
(S3-compatible), aiosmtplib, pyotp (2FA TOTP), passlib+bcrypt, python-jose
(JWT), Sentry SDK.

**Frontend** — React 18 + Vite + TypeScript, react-router-dom, Vitest +
@testing-library, @sentry/react (lazy-loaded).

**Infra** — Docker Compose (dev + prod), nginx + certbot (prod), GitHub Actions
CI (pytest + vitest + docker build).

## Quick start (dev)

Pre-condiții: Docker Desktop.

```bash
cp .env.example .env   # sau editează .env existent
docker compose up -d
```

Disponibile:

| URL                      | Ce e                                       |
| ------------------------ | ------------------------------------------ |
| http://localhost:5173    | Frontend Vite (hot reload)                 |
| http://localhost:8000    | Backend FastAPI (reload on change)         |
| http://localhost:8000/docs | Swagger UI (OpenAPI auto-generated)     |
| http://localhost:9001    | MinIO console (upload/debug pentru Gallery)|

Primul user:

```bash
# Signup via UI pe /signup — devine admin automat pe tenant-ul creat.
# Sau, via API:
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"tenantName":"Acme","email":"you@example.com","password":"parola1234"}'
```

## Teste

```bash
# Backend
docker compose exec backend python -m pytest -q

# Frontend
cd frontend && npm test

# Full CI local (mimic GitHub Actions)
cd frontend && npm test && npm run build
```

Status curent: **95 backend + 63 frontend = 158 teste**.

## Structura proiectului

```
adeplast-saas/
├── backend/              # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── core/         # config, db, security, logging, email, storage
│   │   └── modules/      # un folder per bounded context
│   │       ├── auth/         # login, signup, JWT, refresh, 2FA, invitații
│   │       ├── tenants/      # organizații
│   │       ├── users/        # users + roles (admin/manager/member/viewer)
│   │       ├── stores/       # magazine canonice + aliases
│   │       ├── agents/       # agenți + aliases + assignments
│   │       ├── products/     # produse canonice + aliases
│   │       ├── sales/        # raw_sales + import Excel + export
│   │       ├── dashboard/    # agregări (orchestrator, nu deține date)
│   │       ├── audit/        # imutabil event log + CSV export
│   │       ├── gallery/      # foto-uri via MinIO presigned URLs
│   │       ├── reports/      # Word reports cu charts
│   │       ├── ai/           # AI assistant (Anthropic/OpenAI/xAI/DeepSeek)
│   │       └── api_keys/     # API keys pt access programatic
│   ├── alembic/          # migrații (versionate, auto-descoperite)
│   └── tests/
├── frontend/             # React + Vite
│   └── src/
│       ├── shared/       # api, UI primitives (Skeleton, MergeDialog, ...)
│       └── features/     # un folder per feature (mirror cu backend/modules)
├── nginx/                # nginx.conf.template pentru prod
├── docker-compose.yml    # dev stack
├── docker-compose.prod.yml  # prod stack (nginx + certbot)
└── .github/workflows/ci.yml
```

**Regula modulelor** (strictă): un modul deține tabelele sale; NU face cross-table
JOIN peste module străine. Pentru agregări cross-module, dashboard-ul
orchestrează — preia ID-uri filtrate din `stores.service`, le pasează ca filtru
la `sales.service`. Astfel modulele rămân swappable.

## Arhitectură — principii

- **Canonical entities + alias tables**: `stores`, `agents`, `products` sunt
  entități canonice; `store_aliases` (raw_client → store) sunt mapping imuabil
  cu audit.
- **Raw layer immutable**: `raw_sales` nu se modifică după import. Enrichment
  prin FK-uri nullable (`store_id`, `agent_id`, `product_id`) populate backfill
  când se creează alias.
- **camelCase contracts**: toate Pydantic schema-urile extind `APISchema` care
  generează automat field-uri camelCase pentru JSON. Python-side rămâne
  snake_case.
- **Audit trail**: fiecare acțiune sensibilă scrie în `audit_logs` în aceeași
  tranzacție cu acțiunea (rollback atomic). Endpoint `/api/audit-logs` cu
  filtre + export CSV.

## Deploy production

Vezi [DEPLOY.md](DEPLOY.md).

## Memorie proiect

Context de lucru salvat în `~/.claude/projects/C--Users-Florin-apps/memory/`:
- Deploy workflow (local-only, deploy doar la cerere explicită)
- Strategia canonical + alias
- Arhitectură modular monolith (NU microservicii)
