# Spec — "Analiza pe luni" (module `analiza_pe_luni`)

Status: draft (research-only, nu atinge codul)
Autor: research pe app-ul Flask legacy (`C:\Users\Florin\code\adeplast-dashboard\`)
Data: 2026-04-20

---

## 1. Descriere funcțională

View-ul "Analiza pe luni" (legacy name `dashboard2`) afișează, pentru canalul
KA, **comparativ pe 12 luni** vânzările Y1 (anul precedent) vs Y2 (anul curent),
pentru scope-ul selectat (ADP / SIKA / SIKADP). Pagina are structura:

1. **Section title** — `{SCOPE} — Vanzari Lunare Comparative {Y1} vs {Y2}`.
2. **Total KA** — un panou cu:
   - tabel 12 luni × (Vânzări Y1, Vânzări Y2, Diferență, %),
   - rând TOTAL (sumă anuală),
   - chart bar comparativ Y1 vs Y2.
   - Pentru `scope=sikadp` apar trei panouri: **combinat**, **Adeplast**, **Sika**.
3. **Per client** (nume client KA, sortat alfabetic) — câte un panou
   identic cu "Total KA" pentru fiecare client cu activitate.
4. **Per categorie** (doar `ka_groups` definite per company) — câte un
   panou ca la "Total KA" + imediat dedesubt un **mini-tabel "Top 5
   Produse — {categorie}"**, sortat desc după `sales_y2`, cu coloanele:
   Produs, Vânzări Y1, Vânzări Y2, Diferență, %, Qty Y1, Qty Y2.

Pentru `scope=sikadp` per-client-ul și per-categoria se calculează după
**rezolvarea prin Noemi/SAM** (același pipeline ca Consolidat/Overview),
ca store-urile să fie unificate între ADP și SIKA sub un singur chain
name (vezi `services/consolidat_service.py::get_sikadp_dashboard2_unified`).

## 2. Legacy — referințe

Blueprint + rută:
- `C:\Users\Florin\code\adeplast-dashboard\routes\sales.py:1050`
  `@sales_bp.route("/api/dashboard2")` → `api_dashboard2()`.
- ADP/SIKA (single-scope): logică inline în router, query pe `sales_summary`
  cu `channel='KA' AND UPPER(client) NOT LIKE '%PUSKIN%'`.
- SIKADP: delegat la `services.consolidat_service.get_sikadp_dashboard2_unified`
  — pipeline Noemi mapping, exclude store-urile cu total net = 0.
- Frontend: `templates/index.html:8049` `async function renderDashboard2(main)`
  face fetch la `/api/dashboard2{monthsParam()}` și randează panourile
  + Chart.js bars.

Parametri legacy:
- NU există `year` — scope-ul companiei vine din sesiune
  (`get_company()` → `adeplast` | `sika` | `sikadp`), iar Y1/Y2 sunt
  derivate din `raw_sales`: `SELECT DISTINCT year` → ultimii doi.
- `months` = filtru opțional (listă de luni 1..12), aplicat ca `AND month IN (...)`
  (`svc.get_months_filter()` + `svc.raw_year_cols(months)`).
- Pentru Sika, luna curentă e completată din `exercitiu_cache` (facturat MTD)
  — doar `sales_2026` (Y2), Y1 rămâne din `sales_summary`.

## 3. Contract API propus (SaaS)

```
GET /api/analiza-pe-luni
    ?scope=adp|sika|sikadp
    [&year=YYYY]                 # Y2 (anul curent); implicit = current year
    [&months=1,2,3,...]          # filtru opțional; implicit = 1..12
```

Auth: `tenant_id` via `Depends(get_current_tenant_id)` (ca `vz_la_zi`).
Prefix router: `/api/analiza-pe-luni`, tag `analiza-pe-luni`.

Validări:
- `scope` ∈ {`adp`, `sika`, `sikadp`} — altfel `400 invalid_scope`.
- `year` ∈ [2000, 2100] — altfel `400 invalid_year`.
- `months` — fiecare element ∈ [1, 12]; dacă lipsește → `[1..12]`.
- Y1 = `year - 1` (derivat, NU parametru).

Erori standard: `{code, message}` payload (ca în `vz_la_zi`).

## 4. Structura de răspuns JSON

Shape TypeScript-like (folosește `Decimal` → transport ca `number` sau
`string` — aliniat cu `APISchema` din core; propun `number` pentru a
matcha legacy-ul care deja returnează `float`).

```ts
// ── Atomic row ────────────────────────────────────────────────────
type MonthCell = {
  month: number;          // 1..12
  month_name: string;     // "Ianuarie", "Februarie", ...
  sales_y1: number;       // RON, Decimal
  sales_y2: number;
  diff: number;           // = sales_y2 - sales_y1  (precomputat server-side)
  pct: number;            // = diff / sales_y1 * 100  (0 dacă sales_y1 = 0)
};

// ── Serie 12 luni pentru un dataset ──────────────────────────────
type MonthlySeries = {
  months: MonthCell[];        // exact lunile filtrate, ordonate asc
  total_y1: number;           // Σ months[].sales_y1
  total_y2: number;           // Σ months[].sales_y2
  total_diff: number;
  total_pct: number;
};

// ── Client sau categorie, cu ID-uri canonice ────────────────────
type NamedSeries = {
  id: string | null;          // UUID store/product_category (null = nemapat)
  name: string;               // display name
  series: MonthlySeries;
};

type TopProductRow = {
  product_id: string | null;
  description: string;
  sales_y1: number;
  sales_y2: number;
  diff: number;
  pct: number;
  qty_y1: number;
  qty_y2: number;
};

type CategoryBlock = NamedSeries & {
  top_products: TopProductRow[];   // top 5 sortate desc pe sales_y2
};

// ── Un scope complet (ADP sau SIKA) ──────────────────────────────
type ScopeBlock = {
  total: MonthlySeries;
  clients: NamedSeries[];        // sortat alfabetic pe `name`
  categories: CategoryBlock[];   // sortat alfabetic pe `name`
};

// ── Response principal ──────────────────────────────────────────
type AnalizaPeLuniResponse = {
  scope: "adp" | "sika" | "sikadp";
  year_curr: number;             // Y2
  year_prev: number;             // Y1 (= year_curr - 1)
  months: number[];              // filtrul efectiv aplicat (1..12)
  last_update: string | null;    // ISO datetime (max updated_at din raw_sales în scope)

  // populat când scope ∈ {adp, sika}
  data?: ScopeBlock;

  // populat când scope = sikadp
  combined?: ScopeBlock;         // cu clienți/categorii unificate via SAM
  adeplast?: ScopeBlock;         // subset ADP
  sika?: ScopeBlock;             // subset SIKA
};
```

Regulă de populare:
- `scope=adp` / `scope=sika` → populează doar `data`.
- `scope=sikadp` → populează `combined` + `adeplast` + `sika`; `data` = `undefined`.

## 5. Coloanele din tabel (UI contract)

Tabel principal per panou ("Total KA" / client / categorie):

| Key        | Header (ro)      | Sursă                  | Format               |
|------------|------------------|------------------------|----------------------|
| month_name | Luna             | `MonthCell.month_name` | text                 |
| sales_y1   | Vânzări {Y1}     | `MonthCell.sales_y1`   | RON, 0 zecimale      |
| sales_y2   | Vânzări {Y2}     | `MonthCell.sales_y2`   | RON, 0 zecimale      |
| diff       | Diferență        | `MonthCell.diff`       | RON cu semn, colorat |
| pct        | %                | `MonthCell.pct`        | pct-pill ±%, 1 zec.  |

Rând TOTAL: `total_y1`, `total_y2`, `total_diff`, `total_pct`.

Mini-tabel "Top 5 Produse — {categorie}":

| Key         | Header       |
|-------------|--------------|
| description | Produs       |
| sales_y1    | Vânzări {Y1} |
| sales_y2    | Vânzări {Y2} |
| diff        | Diferență    |
| pct         | %            |
| qty_y1      | Qty {Y1}     |
| qty_y2      | Qty {Y2}     |

## 6. Formulele de calcul

Per lună:
- `diff_month = sales_y2 - sales_y1`
- `pct_month  = (diff_month / sales_y1) * 100` dacă `sales_y1 != 0`, altfel `0`

Per serie (TOTAL):
- `total_y1   = Σ months[].sales_y1`
- `total_y2   = Σ months[].sales_y2`
- `total_diff = total_y2 - total_y1`
- `total_pct  = (total_diff / total_y1) * 100` dacă `total_y1 != 0`, altfel `0`

Aceleași formule se aplică pentru `TopProductRow` (la nivel de produs,
fără dimensiune lunară).

Sortări:
- `clients` → asc pe `name` (legacy: `Object.keys(d.clients).sort()`).
- `categories` → asc pe `name`.
- `top_products` → desc pe `sales_y2` (legacy păstrează), limit 5.

Filtre:
- Mereu `channel = 'KA'`.
- Mereu exclude clienți `UPPER(client) LIKE '%PUSKIN%'` (client de
  test/demo — pattern din legacy; de confirmat dacă trebuie păstrat
  în SaaS sau mutat în config / tag `hidden`).
- `year IN (Y1, Y2)`, `month IN months`.
- `categories` = `ka_groups` per company — în SaaS se ia din
  `product_categories` cu flag `is_ka = true` scope-at pe company
  (nu hardcodat ca în legacy `COMPANY_CONFIG`).

## 7. Dedup SIKA (sika_xlsx + sika_mtd_xlsx)

Identic cu `consolidat.service._fetch_rows` (vezi
`app/modules/consolidat/service.py:67-174`). Rezumat:

- `_scope_sources(company)` returnează grupuri de `batch.source` ordonate
  pe prioritate:
  - `adp`    → `[["sales_xlsx"]]`
  - `sika`   → `[["sika_mtd_xlsx", "sika_xlsx"]]`
  - `sikadp` → `[["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]]`
- Pentru fiecare grup, iterăm surse în ordine și, pentru fiecare
  pereche `(year, month)`, **folosim doar prima sursă care are date**
  (`claimed_pairs`). Astfel MTD > historical pentru aceeași lună.
- Grupurile sunt disjuncte (ADP niciodată nu face dedup cu SIKA), deci
  pentru `sikadp` cele două surse totalizează (merge, nu dedup).
- Luna curentă în SIKA vine de regulă din `sika_mtd_xlsx` (MTD
  facturat) — asta înlocuiește logica legacy cu `exercitiu_cache`.

Consecință pentru "Analiza pe luni":
- Agregările `sales_y1` / `sales_y2` per lună trebuie să respecte
  dedup-ul ACEST — altfel pentru SIKA vom dublu-număra lunile
  acoperite de ambele surse.
- Pentru a evita duplicarea implementării, modulul `analiza_pe_luni`
  poate refolosi un helper extras din `consolidat.service` (ex.
  `consolidat.service._fetch_rows` extins să agrege pe `(month, ...)`
  în loc de `(agent_id, store_id, client)`), sau poate expune un
  helper comun din `sales.service` (ex. `fetch_ka_rows_deduped(tenant_id,
  company, years, months, group_by=["month", ...])`).

## 8. Note arhitecturale / pattern (referință `vz_la_zi`)

- Layout: `router.py` + `service.py` + `schemas.py` + `__init__.py`.
- Router: `APIRouter(prefix="/api/analiza-pe-luni", tags=["analiza-pe-luni"])`.
- Endpoint unic `GET ""` cu `response_model=AnalizaPeLuniResponse`.
- Validare scope la intrare (set `_SCOPES = {"adp", "sika", "sikadp"}`).
- Service returnează dict-uri; router mapează la pydantic `APISchema`.
- Rezolvare canonică: `client_sam_map` + `store_agent_map` + `resolve`
  din `app.modules.mappings.resolution` (ca în `consolidat.service`).
- `Decimal` pentru sume (la fel ca `vz_la_zi.schemas`); conversie la
  `float` doar dacă tot frontend-ul lucrează cu `number`. Propunerea
  de mai sus folosește `number` (`Decimal` serializat ca `number`)
  pentru consistență cu legacy; alternativ `Decimal` → string (la
  fel ca în `vz_la_zi`).
- `last_update` = `MAX(raw_sales.updated_at)` pe scope-ul curent
  (util pentru badge "ultima actualizare" în UI).

## 9. Puncte deschise (de confirmat înainte de implementare)

1. Filtrul `PUSKIN` — rămâne hardcodat sau devine flag pe `stores`?
2. Categoriile KA — sursă: `product_categories.is_ka=true` scoped pe company?
3. `year` default = current year sau = max(year) din `raw_sales`?
   (legacy ia ultimii doi ani din DB — propun același comportament ca
   fallback când `year` lipsește).
4. `top_products` — limit 5 păstrat, configurabil via query `?top_n=`?
5. Pentru `sikadp`, "clients" în `combined` = **chain** (unificat via
   SAM/Noemi) sau set-union brut? Legacy folosește unificare — spec-ul
   păstrează asta.
