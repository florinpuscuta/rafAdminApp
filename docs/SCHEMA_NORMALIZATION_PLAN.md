# Plan de Normalizare a Schemei DB

**Status:** propunere · **Autor:** analiza automatizata · **Data:** 2026-04-25

---

## 1. Rezumat Executiv

Schema actuala (PostgreSQL, ~58 tabele, ~580k randuri in `raw_sales`) sufera
de trei probleme principale:

1. **Concept "tenant" suprasolicitat** — `tenants` este folosit atat pentru
   *organizatie* (Adeplast / Sika), cat si pentru sandbox-uri de test
   ("Test Verify", "TestMobile", "Concurent SRL"). Trebuie reframuit:
   *organizatii* (sau *companii*) pentru entitatile reale Adeplast / Sika /
   Adpsika, separat de useri.
2. **UUID overkill** — toate cheile primare folosesc UUID v4. Pentru un sistem
   single-database, single-tenant-deploy, fara replicare cross-region, INT/
   BIGINT este mai eficient si mai usor de inspectat. UUID se justifica doar
   pentru `users`, `tenants`, tokens si entitati expuse public.
3. **Denormalizare istorica** — `products.category` (string) coexista cu
   `products.category_id` (FK la `product_categories`); `products.brand` cu
   `products.brand_id`; `raw_sales.client` (string) cu `raw_sales.client_code`
   si `raw_sales.store_id`. Sunt artefacte din migrarea legacy → SaaS care nu
   au fost inca curatate.

Acest document propune:
- Reframuirea modelului `tenant` → `organization`
- Migrarea cheilor primare UUID → BIGINT pentru tabelele de business
- Eliminarea coloanelor stringificate redundante
- Roadmap in 5 faze, cu rollback la fiecare pas

---

## 2. Inventarul Curent

### 2.1 Tabelele in 4 categorii

| Categorie | Tabele | Semnificatie |
|---|---|---|
| **Identitate / Auth** | `tenants`, `users`, `refresh_tokens`, `email_verification_tokens`, `password_reset_tokens`, `invitations`, `api_keys`, `app_settings` | Cine se autentifica, sub ce organizatie |
| **Catalog (master data)** | `agents`, `stores`, `products`, `brands`, `product_categories`, `*_aliases`, `store_agent_mappings`, `agent_store_assignments` | Entitati canonice + alias-uri |
| **Tranzactional** | `raw_sales` (580k), `raw_orders` (8.5k), `import_batches`, `production_prices*`, `discount_rules`, `promotions*`, `targhet_growth_pct`, `agent_compensation`, `agent_month_inputs`, `agent_store_bonus`, `store_contact_bonus`, `facturi_bonus_decisions` | Date de business: vanzari, comenzi, costuri, bonusuri |
| **Operational / Periferic** | `gallery_*`, `agent_visits`, `tasks`, `task_assignments`, `activity_problems`, `travel_sheets*`, `panouri_standuri`, `audit_logs`, `ai_*`, `mkt_*`, `facing_*`, `price_*` | Activitate teren, marketing, AI, audit |

### 2.2 Cifre cheie (din BD live)

- 5 inregistrari in `tenants` (din care 3 reale: `Adeplast KA`, `Adpsika`, `Concurent SRL`; restul test)
- 7 useri activi (admins + members)
- 19 agenti, 793 magazine, 2.456 produse
- `raw_sales` = 580.729 randuri (676 MB)
- 11 tabele cu date "live" (>100 rows), 47 tabele cu volume mici sau zero in tenant-uri reale

### 2.3 Dependente UUID critice

`tenants.id` (UUID) este FK cascade in **40+ tabele**. Migrarea PK-ului
necesita reconstructia tuturor FK-urilor — operatie atomica, dar cu
downtime ne-trivial pentru `raw_sales` (580k rows).

---

## 3. Probleme Identificate

### 3.1 Concept "tenant" ambiguu

**Stare curenta:**

```
tenants:
  198f778e... | Adeplast KA       ← organizatie reala
  e6cd4519... | Adpsika           ← organizatie reala (combinata)
  97e14cfc... | Concurent SRL     ← cont demo / test
  72ecc075... | Test Verify       ← test E2E
  55905c2d... | TestMobile        ← test E2E
```

`users.tenant_id` leaga un user la una si numai una din aceste entitati. In
realitate insa:
- `florin@adeplast.ro` (admin Adeplast) ar trebui sa aiba acces la datele
  Adeplast — atat scope `adp` cat si `sikadp` mostenesc din aceeasi organizatie.
- `florin.puscuta@gmail.com` (admin Adpsika) — concept hibrid: combinat ADP+SIKA.

**Problema:** "tenant" amesteca *organizatie* (entitate reala de business)
cu *workspace de test* si nu reflecta corect realitatea: Adeplast si Sika
sunt **doua organizatii distincte** care impart unele date (clientii KA),
iar `Adpsika` este o vedere combinata, nu o organizatie noua.

**Propunere:**

- Renumeste `tenants` → `organizations` (semantic clar)
- Adauga coloana `kind` enum: `production` | `demo` | `test` (separa cele 3
  test/demo de cele 2 reale)
- Schema actuala admite `scope` (adp/sika/sikadp) ca parametru de query —
  pastram, dar NU mai corespunde 1:1 cu organizatia. Adpsika devine vedere
  combinata peste Adeplast + Sika.
- Recomandare avansata (faza 6+): split `Adpsika` in 2 organizatii separate
  (`Adeplast`, `Sika`) cu un mecanism de "joint view" — dar e refactor mare.

### 3.2 Useri = angajati (agenti / financiar)

**Stare curenta:** `users` (cu auth) si `agents` (cu nume, email, telefon)
sunt entitati separate. Un user poate fi admin (acces total) sau member
(nedefinit). `agents` reprezinta agentii de teren — *nu* au cont logic in app.

**Problema:** lipseste rolul explicit pentru:
- Agent de vanzari teren (vede doar magazinele lui)
- Manager financiar (vede toate vanzarile + bonusari)
- Manager regional (zona, mai multi agenti)
- Director (vedere completa)

**Propunere:**

```sql
-- Roluri canonice
CREATE TYPE user_role AS ENUM (
  'admin',           -- root / IT
  'director',        -- vedere completa, organizatie
  'finance_manager', -- vede vanzari + bonusuri, nu poate edita
  'regional_manager',-- vede agentii din zona lui
  'sales_agent',     -- vede magazinele lui
  'viewer'           -- read-only generic
);

-- Link user → agent (1:1 optional)
ALTER TABLE users ADD COLUMN agent_id BIGINT
  REFERENCES agents(id) ON DELETE SET NULL;

-- Pentru regional_manager: lista zone (agenti subordonati)
CREATE TABLE user_managed_agents (
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  agent_id BIGINT REFERENCES agents(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, agent_id)
);
```

Aceasta permite:
- Login `vlad.david@adeplast.ro` → cont user cu role=`sales_agent` legat de
  `agents.id` corespondent → vede doar magazinele lui (via `agent_store_assignments`)
- Login `manager.zona.muntenia@adeplast.ro` → role=`regional_manager` → vede
  agentii din zona lui
- Login `cfo@adeplast.ro` → role=`finance_manager` → toate datele dar fara
  acces edit la mapari/upload

### 3.3 UUID overkill

**Stare curenta:** **toate** PK-urile sunt UUID. Fiecare row are 16 octeti
de cheie + B-tree index pe UUID (slabe pentru insert ordering pe randuri
recente, fragmentat dupa volum mare).

**Cost concret pe `raw_sales`** (580k rows):
- 580k × 16B = ~9.3 MB doar PK
- Plus indexul `raw_sales_pkey`: ~14 MB
- 7 indexuri secundare cu UUID FK (tenant, batch, agent, store, product, ...)
- Total overhead UUID per `raw_sales` ≈ ~80-100 MB

**Cu BIGINT (8 octeti):** overhead-ul se injumatateste.

**Mai important:** UUID ingreuneaza:
- Inspectia manuala (SQL ad-hoc cu `WHERE id = '198f...'` vs `id = 42`)
- Logging/debug (UUID-urile umplu output-ul)
- Generarea de URL-uri scurte (ex: `/produs/EPS100/store/52` vs `/produs/abc-..../store/def-...`)

**Cand UUID se justifica:**

| Tabel | Pastram UUID? | Motiv |
|---|---|---|
| `users` | ✅ DA | Public-facing IDs (URL-uri share, links externe), enumeration prevention |
| `tenants` / `organizations` | ✅ DA | Putine, expuse uneori (subdomains, slug-uri) |
| `refresh_tokens`, `password_reset_tokens`, `email_verification_tokens` | ✅ DA | Securitate (random not guessable) |
| `api_keys` | ✅ DA | API tokens externe |
| `invitations` | ✅ DA | Token in URL pentru registration |
| **Restul (50+ tabele)** | ❌ NU | Internal-only, single-DB, BIGINT mai bun |

### 3.4 Coloane stringificate redundante

**`products`:**
- `category` VARCHAR(100) — denormalizat, exista si `category_id` FK
- `brand` VARCHAR(100) — denormalizat, exista si `brand_id` FK

**`raw_sales`:**
- `client` VARCHAR(255) — coexista cu `store_id` (FK → stores)
- `client_code` VARCHAR(100) — codul SAP / Ship-to, dar valoarea reala e pe
  `stores`
- `agent` VARCHAR(255) — coexista cu `agent_id`
- `product_code` VARCHAR(100), `product_name` VARCHAR(500) — coexista cu
  `product_id`
- `category_code` — coexista cu `products.category_id`

**Justificare istorica:** la import, FK-urile pot fi NULL (produse / clienti
nemapati). Coloanele string pastreaza "raw" textul Excel pentru rezolvare
ulterioara.

**Propunere:** mutam textul raw intr-un tabel separat
`raw_sales_unmapped_text(raw_sale_id, client_text, agent_text, product_text,
...)` care exista doar pentru randurile cu FK NULL. Cand FK e populat, randul
din `raw_sales_unmapped_text` e sters. Castigam ~150 MB pe `raw_sales`.

**Trade-off:** complexitate crescuta la query-uri care raporteaza pe randuri
nemapate. Realist: putem amana faza asta — pierderea de spatiu (~25%) e
acceptabila pentru a pastra simplitatea.

### 3.5 Tabele orfane / suspecte de stergere

| Tabel | Status | Recomandare |
|---|---|---|
| `raw_sales_reassign_backup` (771 rows, 232 KB) | Backup vechi de operatie reasign | Verifica utilitatea; daca nu, drop |
| `price_grid`, `price_grid_meta`, `price_update_jobs` | Modul `prices` (preturi comparative legacy) | Foloseste? Daca nu → drop |
| `panouri_standuri` (213 rows) | Modul `mkt_panouri` | Verifica utilizarea |
| `facing_*` (5 tabele) | Modul `mkt_facing` | Foloseste? |
| `task_assignments` (gol) | Modul `taskuri` | Drop sau pastreaza |
| `app_settings` (cheie/valoare global) | Singleton — N=4 | Pastreaza, e ok |
| `Test Verify`, `TestMobile`, `Concurent SRL` (tenants) | Conturi test pe production | Mutati intr-un DB de staging sau marcati `kind='test'` |

### 3.6 Lipsa `created_by` / `updated_at` pe tabele importante

Multe tabele nu au audit trail elementar:
- `production_prices` are `last_imported_at` dar nu `last_imported_by_user_id`
- `discount_rules` n-are `updated_by` / `updated_at`
- `promotions` are toate dar lipseste pe `promotion_targets`
- `agent_store_assignments` n-are `assigned_by_user_id`

**Propunere:** trigger generic care populeaza `updated_at` pe toate tabelele
cu mod-uri tracked (sau decorare ORM in SQLAlchemy via `onupdate=func.now()`).

---

## 4. Decizia "UUID vs BIGINT" pe Fiecare Tabel

### 4.1 Ramane UUID

```
users, tenants (renamed organizations), refresh_tokens,
email_verification_tokens, password_reset_tokens, invitations, api_keys,
audit_logs.id (pastram pentru trasabilitate cross-system)
```

### 4.2 Devine BIGINT (id si toate FK-urile catre el)

```
agents, stores, products, brands, product_categories,
agent_aliases, store_aliases, product_aliases, product_category_aliases,
brand_aliases, agent_store_assignments, store_agent_mappings,
production_prices, production_prices_monthly, discount_rules,
promotions, promotion_targets,
import_batches, raw_sales, raw_orders, raw_sales_reassign_backup,
agent_compensation, agent_month_inputs, agent_store_bonus,
store_contact_bonus, facturi_bonus_decisions, targhet_growth_pct,
agent_visits, activity_problems, tasks, task_assignments,
travel_sheets, travel_sheet_entries, travel_sheet_fuel_fills,
panouri_standuri, mkt_*, facing_*,
gallery_folders, gallery_photos,
ai_conversations, ai_messages, ai_memory,
price_grid, price_grid_meta, price_update_jobs
```

**Beneficii:** pe `raw_sales` singura, ~80 MB economisiti; query-uri cu
`WHERE id = N` mai rapide; URL-uri lizibile.

---

## 5. Roadmap de Migrare (5 Faze)

Fiecare faza este **independenta** si **rollback-able** prin commit anterior.

### Faza 1 — Reframing semantic (zile)

**Scop:** clarifica modelul mental fara a sparge cod existent.

1. **Migration:** `RENAME TABLE tenants TO organizations` + `ALTER TABLE
   users RENAME COLUMN tenant_id TO organization_id`. Pastram view legacy
   `CREATE VIEW tenants AS SELECT * FROM organizations` pentru compat.
2. **Adauga `organizations.kind` enum**: production / demo / test. Marcheaza
   manual cele 3 demo/test.
3. **Adauga roluri user enum**: extinde `users.role` sau adauga
   `users.role_v2 user_role`. Mapeaza:
   - `admin` → `admin`
   - `member` → `viewer` (default safe)
4. **Adauga `users.agent_id`** (UUID NULL) → leaga useri cu cont la agentii
   canonici. Populeaza manual pentru `vlad.david`, `florin.ioo` etc. (din
   `agents` cu acelasi nume).
5. **Documenteaza**: actualizeaza `README` + `CLAUDE.md` cu noul model
   "organizations".

**Impact cod:** schimbare cosmetica de naming, fara modificare logica. Tot
cod-ul SQLAlchemy ramane functional via aliasuri.

**Risc:** mic. View-ul `tenants` mentine compat. **Rollback:** redenumire
inversa.

### Faza 2 — Cleanup tabele orfane (ore)

**Scop:** scoate ce nu se foloseste, ca migrarea ID-urilor sa fie mai simpla.

1. Audit fiecare modul "candidat la stergere" (vezi 3.5):
   - Daca apare in cod si genereaza date noi → keep.
   - Daca e legacy si nimeni nu l-a accesat de >3 luni → drop migration.
2. `raw_sales_reassign_backup` → drop daca nu e referit.
3. `Test Verify`, `TestMobile`, `Concurent SRL` → mutati pe staging DB sau
   marcati `kind='test'` + filtru pe UI sa nu apara la useri productie.

**Risc:** mic-mediu. Verificare manuala obligatorie inainte de drop.

### Faza 3 — Audit + cleanup denormalizare (1-2 zile)

**Scop:** elimina coloane stringificate redundante.

1. **`products.category`, `products.brand`** — deja avem `category_id`,
   `brand_id`. Migration: `ALTER TABLE products DROP COLUMN category, brand`.
   Verifica intai ca tot codul foloseste FK-urile.
2. **`raw_sales.product_code`, `product_name`, `category_code`** — pot fi
   recuperate via JOIN. Pastram doar pentru randurile **nemapate** (product_id
   NULL). Migration: nullable + populare condit. Optional: muta in
   `raw_sales_unmapped`.
3. **`raw_sales.agent` / `agent_id`, `client` / `store_id`** — la fel.

**Risc:** mediu. Cere update la queries care folosesc string-urile.

### Faza 4 — Adauga audit fields lipsa (ore)

**Scop:** consistenta `created_by_user_id` / `updated_at` peste tot.

1. Adauga `updated_at TIMESTAMPTZ DEFAULT NOW()` cu trigger-uri pe tabelele
   care n-au.
2. Adauga `created_by_user_id` / `updated_by_user_id` unde lipsesc si conteaza.

**Risc:** mic. Aditie pure, fara breakage.

### Faza 5 — Migrare PK UUID → BIGINT (sapere mari, 2-3 zile)

**Scop:** reduce overhead-ul UUID pe tabelele de business.

Aceasta e cea mai grea. Strategie cu zero downtime:

1. **Adauga BIGSERIAL paralel** pe fiecare tabel migrabil:
   ```sql
   ALTER TABLE products ADD COLUMN id_bigint BIGSERIAL UNIQUE;
   ```
2. **Pe FK-uri**, adauga noua coloana paralela:
   ```sql
   ALTER TABLE raw_sales ADD COLUMN product_id_bigint BIGINT;
   UPDATE raw_sales rs SET product_id_bigint = p.id_bigint
   FROM products p WHERE p.id = rs.product_id;
   CREATE INDEX ix_raw_sales_product_id_bigint ON raw_sales(product_id_bigint);
   ```
3. **Schimba SQLAlchemy** sa scrie pe ambele coloane in tranzactie (dual-write
   period).
4. **Validare**: query-uri citesc inca din UUID, scriu in ambele.
5. **Switch read**: schimba SQLAlchemy sa citeasca din `id_bigint`.
6. **Drop UUID columns**: dupa N zile de stabilitate, drop coloana veche +
   rename `id_bigint` → `id`.

**Tabel cu prioritate:** `raw_sales` ultim (mare); incepi cu `agents`,
`stores`, `products`, `brands`, `product_categories`. Apoi
`production_prices`, `discount_rules`, `promotions`. La final `raw_sales` /
`raw_orders`.

**Risc:** mediu-mare. Multe FK-uri. Necesita test E2E inainte si dupa.
Dual-write perioada protejeaza de bug-uri.

**Rollback:** pastreaza UUID-urile pana ai dovedit stabilitatea.

---

## 6. Estimare Effort

| Faza | Estimat | Risc | Beneficiu |
|---|---|---|---|
| 1 — Reframing | 1-2 zile | Mic | Claritate semantica + rolurile user |
| 2 — Cleanup orfane | 4-8 ore | Mic | -10-20% tabele |
| 3 — Denormalizare cleanup | 1-2 zile | Mediu | ~25% spatiu raw_sales |
| 4 — Audit fields | 2-4 ore | Mic | Consistenta |
| 5 — UUID → BIGINT | 2-3 zile | Mare | ~50% spatiu indexuri, query-uri 5-15% mai rapide |

**Total:** ~6-10 zile de lucru pentru migratie completa, in 5 faze
independente.

**Ordine recomandata:**
1. Faza 1 + 2 (paralel) — saptamana 1
2. Faza 3 — saptamana 2
3. Faza 4 — final saptamana 2
4. Faza 5 — saptamana 3-4 (cu dual-write si validare extensiva)

---

## 7. Schema Tinta (extrase)

### 7.1 `organizations` (rebrand `tenants`)

```sql
CREATE TYPE organization_kind AS ENUM ('production', 'demo', 'test');

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(64) NOT NULL UNIQUE,
  kind organization_kind NOT NULL DEFAULT 'production',
  scope_default VARCHAR(10) NOT NULL,  -- adp / sika / sikadp
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  archived_at TIMESTAMPTZ
);
```

### 7.2 `users` cu rol enum

```sql
CREATE TYPE user_role AS ENUM (
  'admin', 'director', 'finance_manager',
  'regional_manager', 'sales_agent', 'viewer'
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  agent_id BIGINT REFERENCES agents(id) ON DELETE SET NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role user_role NOT NULL DEFAULT 'viewer',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  -- ... restul (totp, lockout etc)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ
);

CREATE TABLE user_managed_agents (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  agent_id BIGINT REFERENCES agents(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, agent_id)
);
```

### 7.3 `agents` cu BIGINT PK (exemplu)

```sql
CREATE TABLE agents (
  id BIGSERIAL PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  full_name VARCHAR(255) NOT NULL,
  email VARCHAR(255),
  phone VARCHAR(50),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (organization_id, full_name)
);
```

### 7.4 `raw_sales` (tinta)

```sql
CREATE TABLE raw_sales (
  id BIGSERIAL PRIMARY KEY,
  organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  batch_id BIGINT NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  store_id BIGINT REFERENCES stores(id) ON DELETE SET NULL,
  agent_id BIGINT REFERENCES agents(id) ON DELETE SET NULL,
  product_id BIGINT REFERENCES products(id) ON DELETE SET NULL,
  channel VARCHAR(20),
  amount NUMERIC(14, 2) NOT NULL,
  quantity NUMERIC(14, 3),
  -- text raw doar pentru randuri nemapate (FK = NULL)
  raw_client_text VARCHAR(255),
  raw_agent_text VARCHAR(255),
  raw_product_code VARCHAR(100),
  raw_product_name VARCHAR(500),
  raw_category_code VARCHAR(100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Indexuri pe FK + (year, month) pentru query-uri pe perioada
```

---

## 8. Riscuri si Mitigari

| Risc | Probabilitate | Impact | Mitigare |
|---|---|---|---|
| Faza 5 dual-write produce inconsistente | Medie | Mare | Dual-write cu validare zilnica + rollback la UUID |
| Renaming `tenants` → `organizations` rupe codul | Mica | Mediu | View `tenants AS organizations` pentru compat |
| Migrarea `raw_sales` (580k rows) blocheaza app | Medie | Mare | Migration in batches (10k rows/sec) cu LOCK release intre batches |
| Pierdere date la cleanup (Faza 2) | Mica | Mare | Snapshot DB inainte; verificare cu queries de utilizare |

---

## 9. Concluzie

Schema actuala functioneaza, dar transporta multa "mostenire migrationala"
de la port-ul legacy → SaaS:
- UUID-uri peste tot (cand nu e nevoie)
- Coloane string + FK in paralel
- "Tenant" ca termen umbrella confuz

**Recomand sa incepem cu Faza 1 + 2** (low risk, high clarity gain), apoi
sa evaluam castigul real fata de costul Fazei 5 (UUID → BIGINT) — daca
volumul de `raw_sales` ramane sub 5M rows, beneficiul UUID → BIGINT e
marginal in raport cu efortul. Daca creste la 50M+ rows, devine critic.

**Faza 1 si 2 sunt si auto-suficiente** — nu trebuie sa ne angajam la 5
acum.

---

*Generat ca punct de pornire. Necesita validare cu echipa
inainte de implementare.*
