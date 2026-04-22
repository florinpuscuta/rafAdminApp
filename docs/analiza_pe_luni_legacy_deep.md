# Analiza pe luni (Dashboard 2) — Deep Dive pe aplicația legacy

Source files citite:
- `C:\Users\Florin\code\adeplast-dashboard\templates\index.html` — funcția `renderDashboard2` la L8049-8212
- `C:\Users\Florin\code\adeplast-dashboard\routes\sales.py` — endpoint `/api/dashboard2` la L1050-1193, plus `/api/top_products/<category>` la L1196-1268
- `C:\Users\Florin\code\adeplast-dashboard\services\consolidat_service.py` — `get_sikadp_dashboard2_unified` la L1368-1533
- `C:\Users\Florin\code\adeplast-dashboard\services\config.py` — `COMPANY_CONFIG` (ka_groups, group_labels)
- CSS inline în `templates/index.html` L171-211, 531-545 (mobile)

Data collected: 2026-04-20 (azi). Scopes existente: `adeplast`, `sika`, `sikadp` (combinat).

---

## 1. Overview (ce face dashboard2)

Perspectiva "Analiza pe luni" (nume intern `dashboard2`) este a doua pagină din meniul sidebar "Analiza Vanzari", după `Consolidat` și `Overview`. În acest feature se compară **vânzările KA lunare între Y1 (2025) și Y2 (2026)** pe mai multe niveluri de agregare:

1. **Total KA** — suma tuturor clienților KA pe fiecare lună
2. **Per client KA** — câte un card separat pentru fiecare lanț (Dedeman, Leroy Merlin, Hornbach, Bricostore, Altex etc.)
3. **Per categorie de produs** (doar pentru `adeplast` și `sika` — NU pentru `sikadp`) — câte un card per categorie din `ka_groups`
4. **Top 5 produse per categorie** — doar pentru scope single-company, imediat sub tabelul categoriei părinte

Filtrare: canalul este fix `channel='KA'`, clienții `PUSKIN` sunt excluși (WHERE UPPER(client) NOT LIKE '%PUSKIN%'). Filtre adiționale: `months` (dacă e selectat în topbar), `agent_client_filter` (pentru role=agent → doar clienții lui).

Permisiunea `dashboard2` e activă pentru toate rolurile (admin, manager, agent, observator, cfo).

Menu label: `dashboard2: 'Analiza pe luni'` (L1017 în index.html). Tree child: "Analiza pe luni" (L1165, L1284).

---

## 2. Response JSON shape (câmpuri exacte)

### 2.1. Single-scope (`adeplast` sau `sika`) — `GET /api/dashboard2?months=...`

```jsonc
{
  "total_monthly": [
    {"month": 1, "month_name": "Ianuarie", "sales_2025": 123456.78, "sales_2026": 234567.89},
    // ... câte o intrare per lună care are date
  ],
  "clients": {
    "Dedeman": [ {"month": 1, "month_name": "...", "sales_2025": ..., "sales_2026": ...}, ... ],
    "Leroy Merlin": [ ... ],
    "Hornbach": [ ... ],
    "Bricostore": [ ... ],      // doar Sika
    "Altex": [ ... ]
  },
  "categories": {
    "MU":     [ {"month": ..., "month_name": ..., "sales_2025": ..., "sales_2026": ...}, ... ],  // Adeplast
    "EPS":    [ ... ],
    "UMEDE":  [ ... ],
    "VARSACI":[ ... ]
    // pentru Sika: BUILDING FINISHING, CONCRETE, WATERPROOFING, ROOFING, FLOORING, SEALING & BONDING, ENG. REFURBISHMENT, CONSTRUCTION OTHERS
  },
  "top_products": {
    "MU": [
      {"description": "...", "sales_2025": ..., "sales_2026": ..., "qty_2025": ..., "qty_2026": ...},
      // top 5, deja ordonate DESC by sales_2026 (verificat: `ORDER BY product_category, sales_2026 DESC` la L1183)
    ],
    "EPS": [ ... ],
    ...
  }
}
```

Pe eroare: `{"error": "Raw data not available"}` (status 400) sau `{"error": "..."}`. `categories` poate lipsi per-categorie dacă nu există rânduri.

**Naming convention:** `snake_case` pentru toate câmpurile. Keys numerice `sales_2025` / `sales_2026` sunt hardcoded (nu generice `sales_y1`). Frontendul se uită direct la `m.sales_2025` / `m.sales_2026` — nu e dinamic chiar dacă `companyConfig.years` ar putea fi altele. **Ambiguitate**: Dacă pe viitor anii se schimbă (ex: 2026 vs 2027), numele câmpurilor ar trebui rebotezate — altfel e buggy.

### 2.2. SIKADP (`GET /api/dashboard2` când `session.company == 'sikadp'`)

Procesat de `get_sikadp_dashboard2_unified` (consolidat_service.py L1368).

```jsonc
{
  "sikadp": true,
  "adeplast": {
    "total_monthly": [ {"month": 1, "month_name": "Ianuarie", "sales_2025": ..., "sales_2026": ...}, ... ],
    "clients": { "Dedeman Bacau": [...], "Leroy Merlin Pitesti": [...], ... },
    "categories": {}
  },
  "sika": {
    "total_monthly": [ ... ],
    "clients": { ... },
    "categories": {}
  },
  "total_monthly": [ ... ],    // combinat adp+sika
  "clients": { "chain_name": [...], ... },   // combinat
  "categories": {},            // întotdeauna gol pt sikadp
  "top_products": {}           // întotdeauna gol pt sikadp
}
```

Cheia `chain` pentru clienți = `cheie_finala` din mapping-ul Noemi (`_resolve_key(client, ship_to, source)`), care reprezintă **numele magazinului individual** (ex: "Dedeman Bacau", "Leroy Merlin Pitesti"), nu lanțul părinte. **Ciudățenie**: în scope adp/sika single, keys-urile din `clients` sunt `client` din `sales_summary` (lanț-părinte, ex: "DEDEMAN"), dar în SIKADP sunt per-magazin rezolvate prin Noemi. Granularitatea diferă!

---

## 3. Layout vizual (ordinea cardurilor pe ecran)

Titlu principal (section-title):
- `adeplast`: `"Adeplast - Vanzari Lunare Comparative 2025 vs 2026"`
- `sika`: `"Sika - Vanzari Lunare Comparative 2025 vs 2026"`
- `sikadp`: `"SIKADP - Vanzari Lunare Comparative 2025 vs 2026"`

### 3.1. Scope `adeplast` sau `sika`

Ordinea cardurilor `.perf-panel` (de sus în jos):

1. **Total KA** (id chart `chartD2Total`) — culori chart `rgba(52,152,219,0.7)` (blue) + `rgba(46,204,113,0.7)` (green)
2. **Per client** — ordonat alfabetic `Object.keys(d.clients).sort()` (L8145)
   - chart id: `chartD2Client{i}`
   - culori: rotate dintr-o paletă fixă de 5 perechi (`clientColors`, L8123-8129)
3. **Per categorie**, iterat în ordinea alfabetică `Object.keys(d.categories).sort()` (L8154)
   - Titlu = `companyConfig.group_labels[name] || name` (ex: `MU` → "Mortare Uscate")
   - chart id: `chartD2Cat{i}`
   - IMEDIAT SUB fiecare card de categorie, dacă există `d.top_products[name]`, apare un sub-card **"Top 5 Produse — {label}"** (cu font-size redus). Top-5-ul este re-sortat pe frontend: `[...d.top_products[name]].sort((a,b) => (b.sales_2026||0) - (a.sales_2026||0))` (L8164) — deci sortat DESC după vânzări Y2.

### 3.2. Scope `sikadp`

1. **Total KA — SIKADP (combinat)** — chart `chartD2Total`, culori blue+green
2. **Total KA — Adeplast** — chart `chartD2TotalAdp`, culori `CLR.adpD` (#3a8fd4) + `CLR.adp` (#60b8ff)
3. **Total KA — Sika** — chart `chartD2TotalSika`, culori `CLR.sikaD` (#d97706) + `CLR.sika` (#fb923c)
4. **Per client (combinat)** — alfabetic, iterat din `d.clients` (deci `combined_clients` din backend)
5. Fără categorii și fără top-produse pentru sikadp.

**Ciudățenie:** Deși în response există și `d.adeplast.clients` și `d.sika.clients`, frontend-ul nu le folosește — iterează doar `d.clients` combinat (L8145). Per-brand granularity la nivel de client nu se afișează, doar per total.

### 3.3. Structura HTML pentru FIECARE card (buildSection)

```html
<div class="perf-panel" style="margin-top:16px; border-left:3px solid {clrY2};">
  <div class="perf-header">
    <span class="perf-title" style="color:{clrY2}">{TITLE}</span>
    <span class="delta-badge delta-up|delta-down">{±TOTAL_PCT}%</span>
  </div>
  <div style="overflow-x:auto;">
    <table class="agent-tbl">
      <thead>
        <tr>
          <th>Luna</th>
          <th class="td-r" style="color:{clrY1}">Vanzari 2025</th>
          <th class="td-r" style="color:{clrY2}">Vanzari 2026</th>
          <th class="td-r">Diferenta</th>
          <th class="td-r">%</th>
        </tr>
      </thead>
      <tbody>
        <!-- câte un <tr> per lună + <tr class="total-row"> la final cu TOTAL -->
      </tbody>
    </table>
  </div>
  <div class="chart-wrap" style="max-width:900px;margin:16px auto;">
    <canvas id="{chartId}"></canvas>
  </div>
</div>
```

Border-left colorat apare doar când titlul conține "Adeplast" sau "Sika" (dar NU "SIKADP") — detection-ul e făcut prin `title.includes(...)` (L8072-8073). Adică SIKADP-combinat + clienții individuali NU au border-left (doar "Total KA — Adeplast" și "Total KA — Sika").

---

## 4. Chart specs

- **Biblioteca:** Chart.js (confirmată prin `new Chart(ctx, {...})` și `Chart.defaults.color` la L1857)
- **Tip:** `type: 'bar'`, `indexAxis: 'y'` (bare **orizontale**, thin — via helper `hBarOpts`)
- **Opțiuni:** `responsive: true`, `maintainAspectRatio: false`
- **Bar thickness:** `barThickness: 8`, `borderRadius: 2` (din `thinDs` helper)
- **Labels axa Y:** `m.month_name.substring(0, 3)` (primele 3 caractere din numele lunii — ex "Ian", "Feb", "Mar")
- **Datasets:** două — primul pentru Y1 (2025), al doilea pentru Y2 (2026). Culori passed ca hex (pentru Adeplast/Sika single) sau `rgba(...)` (pentru total/client rotation).
- **Tooltip:** afișează `label + ': ' + fmtNum(raw) + ' RON'` (suffix "RON")
- **Axa X (valori):** format comprimat: `v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(0)+'K' : v`
- **Legendă:** font 11px, boxWidth/boxHeight 10
- **Max width container:** 900px, centrat (`margin:16px auto`)
- **Destroy:** charturile create sunt push-uite în `activeCharts` și distruse la schimbare de view (via `destroyCharts()`)

---

## 5. Formule (toate, cu exemple)

### 5.1. Total row dintr-un tabel monthly

```js
totY1 = Σ m.sales_2025     // peste toate lunile
totY2 = Σ m.sales_2026
totDiff = totY2 - totY1
totPct = totY1 ? (totDiff / totY1 * 100) : 0
```

Ex: totY1 = 100000, totY2 = 120000 → totDiff = 20000, totPct = 20.0% → badge verde `+20.0%`.

### 5.2. Per-rând lunar

```js
diff = m.sales_2026 - m.sales_2025
pct  = m.sales_2025 ? (diff / m.sales_2025 * 100) : 0
```

Când `m.sales_2025 === 0`, `pct = 0` (NU se semnalizează că e growth infinit — ambiguitate, dar e design-ul curent).

### 5.3. Formatting helpers

```js
fmt      = v => v >= 1e6 ? (v/1e6).toFixed(2)+' M' : v >= 1e3 ? (v/1e3).toFixed(0)+' K' : v.toFixed(0)
fmtFull  = v => new Intl.NumberFormat('ro-RO', {maximumFractionDigits:0}).format(v)   // ex: "123.456"
pctStyle = v => v > 0 ? 'color:var(--green);font-weight:600' : v < 0 ? 'color:var(--red);font-weight:600' : ''
pctSign  = v => v > 0 ? '+' : ''      // pentru negative + zero nu adaugă nimic (semnul minus e intrinsec)
```

`fmt` (short) nu e folosit efectiv în tabel (tabelul folosește `fmtFull`); apare doar pentru chart tooltips prin `hBarOpts`.

### 5.4. SQL pentru Total KA (scope single)

```sql
SELECT month,
  COALESCE(SUM(CASE WHEN year=2025 THEN total_sales END),0) AS sales_2025,
  COALESCE(SUM(CASE WHEN year=2026 THEN total_sales END),0) AS sales_2026
FROM sales_summary
WHERE channel='KA'
  AND UPPER(client) NOT LIKE '%PUSKIN%'
  {+month filter}
  {+agent filter}
GROUP BY month
ORDER BY month
```

Analog pentru `clients` (adaug GROUP BY client) și `categories` (adaug `AND product_category IN (...)` + GROUP BY product_category).

### 5.5. SQL pentru Top 5 produse (doar scope single)

```sql
SELECT product_category, description, sales_2025, sales_2026, qty_2025, qty_2026
FROM (
  SELECT product_category, description,
    COALESCE(SUM(CASE WHEN year=? THEN sales END),0) AS sales_2025,
    COALESCE(SUM(CASE WHEN year=? THEN sales END),0) AS sales_2026,
    COALESCE(SUM(CASE WHEN year=? THEN quantity END),0) AS qty_2025,
    COALESCE(SUM(CASE WHEN year=? THEN quantity END),0) AS qty_2026,
    ROW_NUMBER() OVER (PARTITION BY product_category
                       ORDER BY COALESCE(SUM(CASE WHEN year=? THEN sales END),0) DESC) AS rn
  FROM raw_sales
  WHERE channel='KA'
    AND UPPER(client) NOT LIKE '%PUSKIN%'
    AND product_category IN (?, ?, ...)
    {+month filter}
    {+agent filter}
  GROUP BY product_category, description
) sub WHERE rn <= 5
ORDER BY product_category, sales_2026 DESC
```

Top-ul este calculat după **Y2** (sales_2026) DESC. Sursa: `raw_sales` (NU `sales_summary`, care nu are `description`).

### 5.6. SIKADP — agregarea combinată

```python
# _resolve_key normalizează (client, ship_to, source) → cheie_finala din Noemi
# Se construiește store_monthly = {(key, month) → {adp_y1, adp_y2, sika_y1, sika_y2}}
# Adeplast: din sales_summary, toate lunile
# Sika: din sales_summary pentru luni trecute + exercitiu_cache pentru luna curentă
# Filtrare: key este inclus doar dacă key_totals[key] != 0 (elimină store-uri cu 0 total)
# Rezolvare agent: resolve_agent_for_raw_keys(raw_keys) — similar cu Overview/Consolidat

# Output monthly:
total_list[m] = {
  sales_2025: adp_y1 + sika_y1,   # combinat
  sales_2026: adp_y2 + sika_y2
}
adp_list[m] = {sales_2025: adp_y1, sales_2026: adp_y2}
sika_list[m] = {sales_2025: sika_y1, sales_2026: sika_y2}
```

### 5.7. Sika — supliment lună curentă

Pentru scope `sika` (nu `adeplast`), dacă luna curentă (azi = Aprilie 2026 → m=4) e în filtru, backend-ul citește `exercitiu_cache.data` (JSON), și ADAUGĂ la `sales_2026`:
- `total_curr_sales` → total_monthly[current_month].sales_2026
- `clients[*].curr_sales` → clients[cl_name][current_month].sales_2026
- `categories[*].curr_sales` → cats_data[cat_name][current_month].sales_2026

NU se modifică `sales_2025` (se presupune că Y1 pentru luna curentă e deja în sales_summary — ciudățenie: dacă luna curentă nu există încă în sales_summary ca Y1, apare 0 acolo).

Pentru SIKADP, logica analogă e implementată prin `_current_month_invoiced_from_cache(sika_db)` care adaugă atât `curr_sales` (Y2) cât și `prev_sales` (Y1) pentru luna curentă (L1439-1441).

---

## 6. Diferențe ADP vs SIKA vs SIKADP

| Aspect | `adeplast` | `sika` | `sikadp` |
|---|---|---|---|
| Source DB | `adeplast_ka.db` | `sika_ka.db` | ambele, unificate via Noemi mapping |
| Top KA panel | da (1 card: "Total KA") | da (1 card: "Total KA") | 3 carduri: Combinat + Adeplast + Sika |
| Per client label | lanț-părinte (din `client` în sales_summary) | lanț-părinte | magazin individual (cheie_finala Noemi) |
| Per categorie | da (4 grupe: MU, EPS, UMEDE, VARSACI) | da (8 grupe: Building Finishing, Concrete, ...) | **niciodată** (categories={}) |
| Top 5 produse | da | da | **niciodată** (top_products={}) |
| Current month suplement | nu | da (din exercitiu_cache, doar Y2) | da (doar pentru partea Sika a combinatului) |
| Border-left colorat | da (albastru CLR.adp) | da (portocaliu CLR.sika) | doar pentru cardurile "Total KA — Adeplast" și "Total KA — Sika"; combinatul și clienții nu au |
| Filtrul agent | `get_agent_client_filter(db)` aplicat pe sales_summary | idem | Noemi mapping: agent = `resolve_agent_for_raw_keys(raw_keys)`; stores fără agent rămân în totaluri ca "Neatribuit" |
| Filtrul PUSKIN | global (L1075, 1085, 1099, 1180, 1218, 1241, 1254) | global | N/A (sursa e Noemi mapping + exercitiu_cache, nu apare `NOT LIKE '%PUSKIN%'` în consolidat_service; doar la nivel de raw fetcher prin `_store_sales_monthly` — necesită verificare, vezi ciudățenie #4) |

**Ce înseamnă `ka_groups`:** categorii de produs. Definite în `COMPANY_CONFIG[company]['ka_groups']`:
- Adeplast: `['MU', 'EPS', 'UMEDE', 'VARSACI']` → "Mortare Uscate", "Polistiren Expandat", "Tencuieli Umede", "Var si Aci"
- Sika: `['BUILDING FINISHING', 'CONCRETE', 'WATERPROOFING', 'ROOFING', 'FLOORING', 'SEALING & BONDING', 'ENG. REFURBISHMENT', 'CONSTRUCTION OTHERS']`

`group_labels` e mapping `code → display_label` (frontend-ul pickup-uiește `companyConfig.group_labels[name] || name` la L8157).

---

## 7. CSS de reutilizat

```css
/* container card */
.perf-panel { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 18px; }
.perf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; gap: 8px; }
.perf-title { font-size: 15px; font-weight: 700; color: #fff; }

/* badge % la dreapta header-ului */
.delta-badge { display: inline-flex; align-items: center; gap: 2px; padding: 2px 8px; border-radius: 20px; font-size: 12px; font-weight: 700; }
.delta-up   { background: rgba(52,211,153,0.15); color: #34d399; }   /* verde */
.delta-down { background: rgba(239,68,68,0.15);  color: #ef4444; }   /* roșu */

/* tabel lunar */
.agent-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.agent-tbl thead th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 6px 8px; border-bottom: 1px solid var(--border); text-align: left; font-weight: 600; }
.agent-tbl tbody td { padding: 9px 8px; border-bottom: 1px solid rgba(30,41,59,0.5); white-space: nowrap; vertical-align: middle; }
.agent-tbl tbody tr:hover { background: rgba(34,211,238,0.04); }
.agent-tbl .td-r { text-align: right; }
.agent-tbl .total-row td { font-weight: 700; border-top: 2px solid var(--border); font-size: 13px; }

/* pill cu procent pe fiecare rând */
.pct-pill  { display: inline-block; padding: 1px 7px; border-radius: 12px; font-size: 11px; font-weight: 700; white-space: nowrap; }
.pct-green { background: rgba(52,211,153,0.15); color: #34d399; }
.pct-red   { background: rgba(239,68,68,0.15);  color: #ef4444; }
```

Paleta `CLR` (din index.html L1848-1854):
- `adp`  = #60b8ff (Adeplast Y2 — albastru deschis)
- `adpD` = #3a8fd4 (Adeplast Y1 — albastru închis)
- `sika` = #fb923c (Sika Y2 — portocaliu)
- `sikaD`= #d97706 (Sika Y1 — portocaliu închis)
- `total`= #22d3ee (cyan pentru combinat)

Paleta `clientColors` (5 perechi rgba folosite pentru chart-urile pe client, L8123-8129):
```js
[
  ['rgba(231,76,60,0.7)','rgba(241,196,15,0.7)'],
  ['rgba(155,89,182,0.7)','rgba(52,152,219,0.7)'],
  ['rgba(230,126,34,0.7)','rgba(26,188,156,0.7)'],
  ['rgba(52,73,94,0.7)','rgba(149,165,166,0.7)'],
  ['rgba(192,57,43,0.7)','rgba(39,174,96,0.7)'],
]
```

---

## 8. Ciudățenii / ambiguități identificate

1. **Keys hardcoded `sales_2025`/`sales_2026`** în response JSON — dacă în viitor anii comparați devin 2026 vs 2027, numele câmpurilor API trebuie rebotezate sau decuplate (ex. `sales_y1`/`sales_y2` + `years: [y1, y2]` la response). Actualul approach e fragil.
2. **Granularitate inconsistentă pentru `clients` între scope-uri**: adp/sika = lanț-părinte (ex "DEDEMAN"), sikadp = magazin individual (cheie Noemi, ex "Dedeman Bacau"). Pentru rewrite trebuie decis un standard — probabil magazin individual, cu posibilitate de rollup la lanț.
3. **pct = 0 când Y1 = 0**: afișează +0.0% pill verde chiar dacă Y2 > 0 (growth from zero). Ar fi util un format special (ex. "∞" sau "NEW").
4. **PUSKIN filter lipsă în SIKADP**: în `get_sikadp_dashboard2_unified` nu apare `NOT LIKE '%PUSKIN%'` — filtrarea se poate face sau nu în `_store_sales_monthly` (ne-verificat integral). Posibil inconsistent cu scope-urile single. De verificat/aliniat în rewrite.
5. **Sika current month supplement modifică doar Y2**: dacă sales_summary pentru Y1 current month e incomplet, vedem compariții inexacte (Y2 real vs Y1 parțial). Pentru SIKADP există şi `prev_sales` → Y1 current month, deci SIKADP e mai corect decât scope-ul Sika standalone. Inconsistență.
6. **categories={} și top_products={} pentru SIKADP**: funcționalitate lipsă (decizie conștientă? sau TODO nefăcut). Poate fi feature gap de acoperit în SaaS.
7. **Frontend-ul ignoră `d.adeplast.clients` și `d.sika.clients`**: backend-ul trimite perspective per-brand, dar UI-ul iterează doar combinatul. Dead data în response.
8. **`companyConfig` NU este setat pentru `sikadp`** (COMPANY_CONFIG are doar `adeplast` și `sika`) — titlul folosește `titleName = d.sikadp ? 'SIKADP' : companyConfig.name`, deci e gestionat prin flag-ul `d.sikadp`, nu prin config. Dacă scope-urile se extind, pattern-ul e manual.
9. **Border-left verdict**: logica `title.includes('Sika') && !title.includes('SIKADP')` e fragilă — dacă un client se cheamă "Sika Center" ar primi border-left portocaliu. În practică nu e o problemă acum, dar e cod înșelător.
10. **Top 5 produse re-sortate pe client**: backend-ul trimite deja sortat DESC by sales_2026 (SQL `ORDER BY product_category, sales_2026 DESC`), frontend-ul re-sortează (defensiv). Dublare ne-necesară.
11. **`esc()` aplicat pe `p.description`** (L8177) — bine (XSS safe), dar truncare la 50 caractere făcută ÎNAINTE de esc → dacă truncare taie în mijlocul unei entități HTML `&amp;` ar apărea textual; în practică descrierile nu conțin escape-uri, dar e de reținut.

---
