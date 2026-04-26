# sales

Modulul deține `raw_sales` — sursa de adevăr a tuturor liniilor de vânzare
brute, importate din Excel-uri ADP și Sika. Acoperă întregul flux de import
(parse XLSX → normalizare canonicals din Alocare → ștergere conflicte →
bulk insert chunked → backfill FK store/agent/product), listare paginată,
export Excel și management de batch-uri. Importul rulează async cu
progres pe etape (`/import/jobs/{id}`). Valorile listate / agregate sunt
filtrate strict pe `channel='KA'` — Retail/RT e exclus by design.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/sales` | Listare paginată raw_sales (filtre: storeId, agentId, productId, year). |
| POST | `/api/sales/import` | Import sincron .xlsx ADP — folosit doar pentru fișiere mici / dev. |
| POST | `/api/sales/import/async` | Import async (recomandat). Acceptă `source=adp\|sika\|sika_mtd`. Returnează `job_id`. |
| GET | `/api/sales/import/jobs/{job_id}` | Status job: stages cu `progress`/`done`, `overall_progress`, `result` la final. |
| POST | `/api/sales/backfill` | Re-rulează backfill FK (store_id, agent_id) pe rândurile existente — pentru ADP și SIKA. |
| GET | `/api/sales/export` | Export .xlsx cu toate raw_sales (filtru opțional `year`/`month`). |
| GET | `/api/sales/batches` | Listă batch-uri de import ordonate desc după dată. |
| DELETE | `/api/sales/batches/{batch_id}` | Șterge batch-ul + toate raw_sales asociate (CASCADE). |

## Tables

- **`import_batches`** — un upload XLSX = un batch. `source` (`sales_xlsx` /
  `sika_xlsx` / `sika_mtd_xlsx`) izolează ADP de SIKA pentru ștergeri scoped.
- **`raw_sales`** — linie individuală de vânzare. Coloane raw imuabile
  (`client`, `agent`, `product_code/name`) + FK nullable la canonicals
  (`store_id`, `agent_id`, `product_id`) populate la backfill. `client_code`
  (cod ship-to numeric) e folosit ca match primar pentru SIKA.

Notă: jobs-urile sunt in-memory (`sales/jobs.py`), NU persistate în DB —
se pierd la restart de proces.

## Cache & invalidation

Importul invalidează tot cache-ul de agregate al tenant-ului prin
`cache.invalidate_tenant(tenant_id)` la finalul stage-ului `finalize` (vezi
`import_service.py`). Fail-soft: dacă Redis e jos, log + ignore. Cache-uri
afectate: `consolidat:*`, `marja_lunara:*`, `top_produse:*`, etc. — toate
agregările pe `raw_sales` cu prefix tenant.

## Dependencies

- **`stores`** — `resolve_map` (raw client → store_id), `create_store`,
  `create_alias` la normalizare Alocare.
- **`agents`** — `resolve_map`, `create_alias`, `AgentStoreAssignment`
  upsert din sheet Alocare.
- **`products`** — `resolve_map` (cod articol → product_id).
- **`mappings`** — backfill FK pentru ADP (match pe nume combined) și SIKA
  (primar pe `cod_numeric`, fallback pe nume).
- **`audit`** — log la `sales.batch_imported`, `sales.backfill_fks`,
  `sales.batch_deleted`.
- **`evaluare_agenti`** — `apply_facturi_bonus_rule_all` rulat automat
  după fiecare import.
- **`tenants.Organization`** — guard org-source la `/import/async` (sursa
  trebuie să corespundă slug-ului org-ului activ).

## Quirks / gotchas

- **Channel filter**: tot ce listează / agregă filtrează `UPPER(channel) =
  'KA'`. Datele non-KA rămân în DB dar nu apar nicăieri în UI.
- **Sika dual-source dedup MTD > historic**: la `source=sika` se șterg
  rândurile DIN AMBELE `sika_xlsx` ȘI `sika_mtd_xlsx` pentru perechile
  (year, month) ale fișierului — fiecare upload SIKA îl înlocuiește pe
  celălalt pe lunile suprapuse.
- **Sika nu are sheet Alocare** — agenții pe SIKA se rezolvă 100% prin
  SAM la backfill (cod ship-to primar, nume fallback).
- **Strict mode pe Alocare**: `_normalize_alocare` aruncă
  `_ImportAborted(code='unknown_agents')` dacă întâlnește un nume de
  agent care NU există ca `Agent.full_name` sau `AgentAlias.raw_agent`.
  Nu mai se creează agenți "fantomă" pe typo.
- **Sinteza client + ship_to**: ADP și Sika ambele combină client +
  ship_to ca `"{client} | {ship_to}"` în `raw_sales.client` — așa rezolvă
  alias-urile unic. Store-ul canonic e la nivel de punct de livrare.
- **Concurrency guard**: există maxim un job activ per tenant
  (`has_active_job`). 409 dacă încerci un al doilea import în paralel.
- **Header autodetect ADP**: parser-ul caută printre primele 20 rânduri
  un rând cu cel puțin 3 din `{year, month, client, amount}` — fișierele
  reale au merged cells / titluri înainte de header.
