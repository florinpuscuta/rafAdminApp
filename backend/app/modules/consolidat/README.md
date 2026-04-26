# consolidat

Modul de raportare "Consolidat KA" — agregare Y1 vs Y2 pe `channel='KA'`,
pe scope de companie (`adeplast` / `sika` / `sikadp`). Citește din
`raw_sales` + `import_batches` (filtrând pe `source`), aplică rezolvare
canonicală agent/store via SAM (`mappings.resolution`) și expune două
nivele: total & defalcare per agent, plus drill-down pe magazinele unui
agent. Pentru `sikadp` agregă cross-org (Adeplast + Sika), iterând pe
toate `org_ids` și deduplicând după **numele** agentului / magazinului.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/consolidat/ka` | Totaluri Y1/Y2 + listă agenți. Params: `company`, `y1`, `y2`, `months` (CSV). Default y2=anul curent, y1=y2-1, months=YTD până la luna curentă. |
| GET | `/api/consolidat/ka/agents/{agent_id}/stores` | Defalcare magazine pentru un agent (sau `agent_id="none"` pentru rândurile fără agent rezolvat). |

Răspunsul include `period_label` formatat RO ("YTD — Ian → Apr") și
flag-ul `include_current_month`.

## Tables

Modulul **nu deține tabele proprii**. Citește exclusiv din:

- `raw_sales` (modulul `sales`) — sursa de date.
- `import_batches` (modulul `sales`) — folosit pentru a izola scope-ul
  per companie via `source` (`sales_xlsx` = Adeplast, `sika_xlsx` /
  `sika_mtd_xlsx` = Sika).
- `store_agent_mappings` (modulul `mappings`) — pentru rezolvare SAM.
- `agents`, `stores` (module omonime) — hidratare nume.

## Cache & invalidation

Funcția grea `_resolved_rows` e cache-uită cu prefix `consolidat:resolved`
și cheie `{tenant_id}:{company}:{y1}:{y2}:{months_csv}` (vezi `_agg_key`).
TTL provine din `cache_ttl_aggregates`. Cache-ul se invalidează automat la
import în `raw_sales` via `cache.invalidate_tenant(tenant_id)` — orice
modificare de date refreshează la următorul GET.

## Dependencies

- **`sales`** — `RawSale`, `ImportBatch` (citite direct cu select).
- **`mappings.resolution`** — `client_sam_map`, `store_agent_map`,
  `resolve` pentru rezolvarea canonică (agent_id, store_id) per rând.
- **`agents`** — `agents_service.get_many` pentru hidratare nume agenți.
- **`stores`** — `stores_service.get_many` pentru hidratare nume / chain
  / city magazine.
- **`tenants.Organization`** — citit indirect prin `org_ids` din auth.
- **`auth.deps.get_current_org_ids`** — toate org-urile la care user-ul
  are acces (esențial pentru SIKADP multi-org).

## Quirks / gotchas

- **Scope SIKA dedup MTD > historical**: pentru `company=sika`,
  `_fetch_rows` parcurge sources în ordinea `['sika_mtd_xlsx',
  'sika_xlsx']` și CLAIMS perechile (year, month) — al doilea source nu
  mai aduce rânduri pentru lunile deja acoperite de MTD. Asta evită
  dublarea când istoric și MTD se suprapun.
- **SIKADP nu deduplică între ADP și SIKA** — sunt grupuri separate de
  sources, însumate. `[['sales_xlsx'], ['sika_mtd_xlsx', 'sika_xlsx']]`.
- **store_ids sunt tenant-scoped**: la SIKADP același magazin fizic are
  UUID diferit în Adeplast vs Sika. Router-ul deduplică **pe nume** —
  un magazin care apare în ambele orgs (ex. "DEDEMAN BACAU 23") se
  numără o singură dată în `stores_count`.
- **Agent matching cross-org la drill-down**: pentru
  `/agents/{agent_id}/stores` în SIKADP, router-ul rezolvă numele
  agentului în org-ul de origine, apoi caută agentul cu același
  `full_name` în fiecare celălalt org și sumează.
- **`agent_id="none"`** literal e cale validă pentru bucket-ul "Nemapați"
  (rândurile cu agent_id NULL după rezolvarea SAM).
- **`pct_change` returnează 0.0 când y1=0** — evită division by zero, dar
  un magazin nou (Y1 zero, Y2 pozitiv) apare ca `pct=0` în UI. UI-ul
  trebuie să detecteze și să afișeze "(nou)" separat.
- **months gol = YTD**: dacă `months` query param e absent, default e
  `[1..luna curentă]` doar pentru `/ka` (nu și pentru `/agents/.../stores`,
  unde tot YTD se aplică prin `default_to_ytd=True`).
