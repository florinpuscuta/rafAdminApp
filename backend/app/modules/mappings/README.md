# mappings

Modul SAM (Store/Agent Mapping) — sursa unică de adevăr pentru rezolvarea
de la tuple-ul raw `(source, client_original, ship_to_original)` la
canonicalul unificat `(cheie_finala → Store, agent_unificat → Agent)`.
Alimentat din fișierul Raf `mapare_completa_magazine_cu_coduri_v2.xlsx`
(sau editat manual prin CRUD-ul `/api/mappings`). Înlocuiește vechea
logică bazată pe sheet-ul Alocare — fiind sursă unificată ADP + SIKA,
elimină discrepanțele de nume agent între cele două surse. Orice
modificare CRUD (POST / PATCH / DELETE) re-rulează backfill-ul pe
`raw_sales` ca FK-urile să reflecte starea curentă.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/mappings` | Listă toate SAM-urile (filtru opțional `source=ADP\|SIKA`). |
| GET | `/api/mappings/unmapped` | Distinct (client, ship_to) din raw_sales KA care nu au SAM cu agent — pentru UI alocare rapidă. Param `scope=adp\|sika`. |
| POST | `/api/mappings/upload` | Upload fișier Raf. Parse + upsert + creare canonicals + backfill ADP. |
| POST | `/api/mappings` | Creare manuală mapping (validează agent strict). Re-backfill pe sursa creată. |
| PATCH | `/api/mappings/{mapping_id}` | Update mapping. Re-backfill pe sursa rezultată. |
| DELETE | `/api/mappings/{mapping_id}` | Șterge mapping. Re-backfill ADP. |

## Tables

- **`store_agent_mappings`** — un rând per (tenant, source, client_original,
  ship_to_original) cu unique constraint. Conține:
  - cheia naturală: `source`, `client_original`, `ship_to_original`
  - canonical-uri: `cheie_finala`, `agent_unificat`
  - FK-uri populate la ingest: `store_id`, `agent_id`
  - audit: `agent_original`, `cod_numeric` (ship-to numeric Sika).

Modulul **nu** deține `stores` / `agents` — doar le creează prin
`Store(...)` / referă `Agent.id` (strict, fără auto-create).

## Cache & invalidation

Modulul nu menține un cache propriu, **dar invalidează indirect** toate
agregatele: orice schimbare CRUD apelează `backfill_raw_sales` care
modifică `raw_sales.store_id/agent_id` — rapoartele cache-uite (consolidat,
marja_lunara, etc.) trebuie reconstruite. În flow-ul curent invalidarea se
face implicit prin următorul import în `raw_sales` (`cache.invalidate_tenant`).
**TODO**: invalidare explicită după mutarea SAM ar fi safer.

`client_sam_map` și `store_agent_map` din `resolution.py` sunt apelate
**per request** de toate modulele de raportare (consolidat, sales.sum_by_agent,
etc.) — fac un SELECT pe SAM la fiecare call, fără cache local. Pentru
tenanți cu sute de SAM-uri (cazul tipic) costul e ~5-20ms.

## Dependencies

- **`stores`** — `Store` model creat la ingest când `cheie_finala` e nouă
  (chain = client_original, city = ship_to_original).
- **`agents`** — `Agent` lookup strict prin `full_name` exact sau
  `AgentAlias.raw_agent`. **NU creează agenți fantomă** —
  `UnknownAgentError` blochează ingest-ul / CRUD-ul.
- **`agents.AgentStoreAssignment`** — folosit în `store_agent_map` ca
  fallback când SAM nu acoperă un raw store_id.
- **`sales`** — `RawSale`, `ImportBatch` modificate de `backfill_raw_sales`
  via UPDATE ... FROM pe match scoped pe `import_batches.source`.
- **`audit`** — log la `mappings.uploaded`, `mappings.created`,
  `mappings.updated`, `mappings.deleted`.

## Quirks / gotchas

- **`client_sam_map` indexează după DOUĂ chei** pentru același rând SAM:
  - `UPPER(client_original | ship_to_original)` (raw, ex. ADP)
  - `UPPER(client_original | cheie_finala)` (canonical, ex. Sika orders
    care vin cu numele canonic).
  Asta unifică multiple format-uri de raw fără să dublezi SAM-ul.
- **Backfill SIKA dual**: PRIMAR pe `rs.client_code = m.cod_numeric`
  (ship-to numeric, stabil între exporturi) — populat pe ~203/209 mapări
  SIKA. Apoi FALLBACK pe `rs.client = m.client_original || ' | ' ||
  m.ship_to_original` pentru rândurile rămase.
- **Backfill ștergere defensivă**: înainte să facă UPDATE, `backfill_raw_sales`
  setează `store_id = NULL, agent_id = NULL` pe toate rândurile sursei
  curente (`b.source = :bsrc`). Fără asta, dacă un cheie_finala se
  redenumește în Raf, vechea legătură ar persista.
- **Scope source izolat**: backfill-ul ADP NU atinge rândurile SIKA și
  vice-versa — match-ul e prin `import_batches.source` (sales_xlsx vs
  sika_xlsx).
- **Strict mode pe agenți la ingest**: `ingest_mapping_rows` aruncă
  `UnknownAgentError` cu lista exactă de agenți necunoscuți dacă
  `agent_unificat` nu match-uiește un Agent sau alias. User-ul trebuie
  să adauge alias / creeze agentul manual înainte de re-upload.
- **Upload-ul declanșează backfill DOAR pe ADP**: dacă upload-ul aduce
  mapări SIKA noi, trebuie apelat manual `POST /api/sales/backfill`
  pentru SIKA — sau aștepta următorul import SIKA care invocă
  `sales_backfill.run_full_backfill(source='SIKA')`.
- **`list_unmapped`**: SQL crud SPLIT_PART/SUBSTRING pe
  `' | '` extrage componentele din `raw_sales.client` (sintetizat la
  import). Dacă format-ul se schimbă, query-ul trebuie revizitat.
- **`norm_client_key`**: cheia normalizată = `UPPER(TRIM('CLIENT |
  SHIP_TO'))`. Strict pe formatul cu spațiu-pipe-spațiu — orice
  divergență ("CLIENT|SHIP" sau "CLIENT  |  SHIP") nu match-uiește.
