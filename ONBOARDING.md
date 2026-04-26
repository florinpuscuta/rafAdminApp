# Onboarding — developer guide

Citește înainte să începi să lucrezi pe rafAdminApp / Adeplast SaaS.
Pentru deploy citește `DEPLOY.md`. Pentru operare zilnică (importuri,
exporturi) citește `docs/PLAYBOOK_IMPORTS.md`.

---

## 1. Setup local (15 min)

Pre-condiții: **Docker Desktop**, **git**, **Node 20+** (doar pentru
type-checks în afara containerului). Restul e încapsulat în Docker.

```bash
git clone git@github.com:florinpuscuta/rafAdminApp.git
cd rafAdminApp
cp .env.example .env   # editează valorile minime: JWT_SECRET, MINIO_*
docker compose up -d   # ridică db + minio + redis + backend + frontend
```

Verificare:

| URL                          | Ce trebuie să vezi                       |
| ---------------------------- | ---------------------------------------- |
| http://localhost:5173        | UI-ul SaaS (login)                       |
| http://localhost:8000/docs   | Swagger UI cu toate endpoint-urile       |
| http://localhost:8000/api/health | `{"status":"ok"}`                    |
| http://localhost:9001        | MinIO Console (login: admin/admin local) |

Primul user (admin pe tenant nou): UI → Sign up. Sau via API:

```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"tenantName":"Acme","email":"you@example.com","password":"parola1234"}'
```

---

## 2. Hartă codebase (5 min)

```
backend/app/
├── core/                    # cross-cutting (config, db, security, cache, metrics)
│   ├── cache.py             # Redis wrapper (cached / cached_pydantic / invalidate_tenant)
│   ├── metrics.py           # slow queries + cache hit/miss + endpoint admin
│   ├── registry.py          # singura listă de routere — include_router în main.py
│   └── ...
├── modules/                 # un folder per "bounded context"
│   ├── auth/                # JWT, signup, refresh, 2FA TOTP
│   ├── tenants/             # organizații (renumit din "tenants")
│   ├── users/               # users + roles
│   ├── stores/, agents/, products/   # entități canonice + alias-uri
│   ├── sales/               # raw_sales + import xlsx + backfill FK
│   ├── consolidat/          # agregat KA Y1 vs Y2 (heavy — cache-uit)
│   ├── margine/, marja_lunara/, top_produse/, ...   # rapoarte
│   ├── ai/                  # Claude/OpenAI/xAI/DeepSeek + tool-use SQL
│   ├── admin_metrics/       # GET /api/admin/metrics
│   └── ...
└── alembic/versions/        # migrații (auto-applied la docker startup în prod)

frontend/src/
├── shared/                  # api client, UI primitives
└── features/                # mirror cu backend/modules/

docs/                        # specs + playbooks
```

Reguli arhitecturale:

1. **Un modul deține tabelele lui.** Nu face `JOIN` cross-module direct
   în service-ul tău; cere ID-uri filtrate de la modulul vecin și
   filtrează cu `IN (...)` sau cere o funcție publică.
2. **Camelcase la API, snake_case în DB / Python.** `APISchema` din
   `core/schemas.py` setează automat `populate_by_name + alias_generator`.
3. **Tot ce e tenant-scoped trece prin `Depends(get_current_user)`** (sau
   `get_current_admin`) și filtrează DB-ul după `tenant_id`. Nu există
   row-level security în Postgres — îl impunem la nivel de query.
4. **Operații ireversibile** (`DROP`, `DELETE` masiv, fișiere șterse) se
   loghează în `audit_logs`. Vezi `app.modules.audit`.

---

## 3. Workflow zilnic

### A. Adaugă un modul nou

1. `backend/app/modules/<nume>/__init__.py` (gol)
2. `models.py` — clase `Base` (în `core/db.py` Base e auto-importat la
   alembic autogenerate)
3. `schemas.py` — Pydantic `APISchema` pentru API contracts
4. `service.py` — logica de business (async)
5. `router.py` — `from app.core.api import APIRouter`
6. **Înregistrează** în `app/core/registry.py`:
   ```python
   from app.modules.numemodul.router import router as numemodul_router
   MODULE_ROUTERS = [..., numemodul_router]
   ```
7. **Migrație**:
   ```bash
   docker compose exec backend alembic revision --autogenerate \
     -m "add numemodul tables"
   docker compose exec backend alembic upgrade head
   ```
8. **Test**: `backend/tests/test_numemodul.py` cu fixture-ul `admin_ctx`
   din `conftest.py`.
9. **Frontend**: `frontend/src/features/numemodul/` (mirror la backend).
   Adaugă entry în `routes.tsx` + `Shell.tsx` (nav).

### B. Modifică o coloană

1. Schimbă `models.py`.
2. `alembic revision --autogenerate -m "..."` — verifică SQL generat
   manual (autogen e frecvent imperfect, mai ales la `Numeric` precizie
   sau `nullable`).
3. Test local: `alembic upgrade head` apoi `alembic downgrade -1` —
   amândouă trebuie să meargă.

### C. Adaugă cache pe un agregat greu

În `service.py`:

```python
from app.core.cache import cached, months_csv

def _key(session, tenant_id, *, scope, year, month):
    return f"{tenant_id}:{scope}:{year}:{month}"

@cached(prefix="modul:agregare", key_fn=_key)
async def heavy_aggregate(session, tenant_id, *, scope, year, month):
    ...
```

Cache-ul se invalidează automat la import în `raw_sales` (vezi
`sales/import_service.py`). Dacă agregatul depinde de altceva, adaugă
invalidare explicită cu `invalidate_tenant(tenant_id)`.

### D. Adaugă o metrică nouă

Slow queries și cache hit/miss sunt deja monitorizate. Pentru o metrică
custom, vezi `app/core/metrics.py` — extinzi `_SlowQueryStats` sau adaugi
counter Redis cu prefix `metrics:<categorie>:`.

---

## 4. Testing

```bash
# Toate testele backend
docker compose exec backend python -m pytest -q

# Un singur test
docker compose exec backend python -m pytest tests/test_sales.py::test_import -xvs

# Frontend
cd frontend && npm test

# Type-check fără container
cd frontend && npx tsc --noEmit
```

Scriere test:
- Folosește `client: AsyncClient` + `admin_ctx`/`signup_user` din
  `conftest.py`.
- Pentru date de test, `tests/_helpers.py:sample_row()` + `make_xlsx()`.
  `channel="KA"` e default — dacă schimbi, listările `/api/sales` nu vor
  vedea rândurile (filtru `_ka_filter`).
- DB-ul de test e curățat între teste prin TRUNCATE (vezi
  `conftest._cleanup_after_test`).
- Cache-ul Redis e dezactivat în teste (`CACHE_ENABLED=False`).

---

## 5. Debugging

### Backend logs

```bash
docker compose logs -f backend
```

Format JSON cu `request_id` corelabil în Sentry (dacă DSN setat).

### Slow queries

`GET /api/admin/metrics` (admin auth) → secțiunea `slow_queries.top`.
Threshold default 500ms; configurabil prin `SLOW_QUERY_THRESHOLD_MS`.

### Cache

`/api/admin/metrics` → secțiunea `cache` cu hit-rate per prefix.

```bash
# Verifică direct în Redis
docker compose exec redis redis-cli
> SCAN 0 MATCH "agg:*" COUNT 100
> KEYS metrics:cache:*
```

### AI cost

`/api/admin/metrics?days=30` → `ai_cost.by_tenant_model`.

### Frontend

DevTools → Network. Endpoint-urile întorc `request_id` în header
`X-Request-Id` — îl folosești ca să cauți în Sentry / logs.

---

## 6. Dual-path setup (specific lui Florin)

Sursa de adevăr e `C:\Users\Florin\ghProjects\rafAdminApp` (git, IDE).
Stack-ul Docker rulează din `C:\Users\Florin\code\adeplast-saas` (volum
mount). La schimbări, sincronizează manual fișierele schimbate:

```bash
# Pentru un fișier
cp /c/Users/Florin/ghProjects/rafAdminApp/backend/.../foo.py \
   /c/Users/Florin/code/adeplast-saas/backend/.../foo.py
```

Backend-ul are `--reload` în dev — pickup imediat. Pentru deps noi
(requirements.txt), trebuie `docker compose up -d --build backend`.

Pentru deploy prod, vezi `DEPLOY.md` (scp + docker compose rebuild pe
Hetzner).

---

## 7. Resurse

- `README.md` — quick start + stack overview
- `DEPLOY.md` — deploy production pas cu pas
- `docs/PLAYBOOK_IMPORTS.md` — operare zilnică (importuri, mapări)
- `docs/SCHEMA_NORMALIZATION_PLAN.md` — viziune long-term DB normalization
- `docs/analiza_pe_luni_spec.md` — exemple de specuri de feature

---

**Versiune**: 1.0 (2026-04-26)
**Reviewer**: Florin Pușcuța
