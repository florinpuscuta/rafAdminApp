# Spec — "Comenzi fara IND" (module `comenzi_fara_ind`)

Status: draft (research-only, nu atinge codul)
Autor: research pe app-ul Flask legacy (`C:\Users\Florin\code\adeplast-dashboard\`)
Data: 2026-04-20

---

## 1. Descriere funcțională

View-ul "Comenzi fara IND" afișează, pentru **scope ADP** exclusiv, liniile
de comandă deschise (radiografie / radComenzi) care **nu au IND** populat.
IND = indicativ comercial de negociere emis pentru fiecare comandă confirmată
cu lanțul (KA); o comandă fără IND semnalează:

- ori o omisiune operațională a agentului (trebuie să-l obțină),
- ori o comandă care nu a fost încă legată la un deal / alocare.

Managerul (rol `admin`/`manager`) folosește pagina pentru:
1. a vedea valoarea totală în RON a comenzilor fără IND (risc pentru target),
2. a distribui comenzile **neatribuite** către agenți (assignment manual),
3. a exporta CSV/XLS per agent (lista e trimisă ca to-do agentului).

Pagina are structura:

1. **Header** — titlu `Comenzi fara IND — {luna} {an}` + `Actualizat: {cached_at}`.
2. **KPI cards** (4): `NR. COMENZI`, `VALOARE TOTALA` (RON), `CANTITATE TOTALA` (buc),
   `NEATRIBUITE` (doar manager — count din bucket `Neatribuit`).
3. **Situatie pe agenti** — tabel sumar:
   Agent | Nr. Comenzi | Nr. Magazine | Valoare (RON) | Cantitate.
   Sortare: `Neatribuit` primul, apoi desc după `total_suma`.
4. **Detaliu comenzi pe agent** — secțiuni collapsible per agent
   (header galben / roșu pentru `Neatribuit`), cu buton `XLS` per secțiune.
   În interiorul fiecărei secțiuni, comenzile sunt **grupate pe
   `(nr_comanda, chain, ship_to)`** cu:
   - header comandă: chain — ship_to, nr_comanda (mono), client, n linii,
     total valoare RON, total buc.
   - (manager only) bandă galbenă de assignment: `select Agent` + `input Note` + `Salveaza`.
   - tabel linii produs: Produs | Tip | Cant. Rest. | Valoare | Data Livrare | Status.

Nu e disponibilă pentru rolul `observator` (ascuns prin `hideAgents()` în JS).
SIKA / SIKADP nu au IND — butonul din sidebar nu apare pentru aceste scope-uri.

## 2. Legacy — referințe

Blueprint + rute (thin):
- `C:\Users\Florin\code\adeplast-dashboard\routes\exercitiu.py:111`
  `@exercitiu_bp.route("/api/comenzi_fara_ind", GET)` → `svc.get_comenzi_fara_ind(...)`.
- `C:\Users\Florin\code\adeplast-dashboard\routes\exercitiu.py:120`
  `@exercitiu_bp.route("/api/comenzi_fara_ind/assign", POST)` → `svc.assign_comenzi_fara_ind(...)`.
  Restricționat la rolurile `admin` / `manager`.

Service (logică):
- `C:\Users\Florin\code\adeplast-dashboard\services\exercitiu_service.py:386-441`
  — în `process_adeplast_exercitiu`, la parsarea fiecărei linii:
  - `ind_val = row[16]`
  - `has_ind = bool(ind_val and str(ind_val).strip() not in ('', 'nan', 'None'))`
  - dacă `not has_ind` și linia **nu** e skipped (rules: NELIVRAT + `cant_rest <= 0`
    → skip; NEFACTURAT → always include), se adaugă în `comenzi_fara_ind` cu
    `suma_rest` calculat identic (proporțional pt. NELIVRAT, full pt. NEFACTURAT).
- `services/exercitiu_service.py:642-710` — enrichment cu manual assignments
  + auto-assign din Noemi (`mapping_service.resolve_agent('ADP', client, ship_to)`).
  Rezultatul serializat e salvat în `exercitiu_adeplast_cache.data` (JSON) sub
  cheia `comenzi_fara_ind`.
- `services/exercitiu_service.py:770-861` — `get_comenzi_fara_ind(agent_filter)`
  citește cache-ul, re-overlay manual + Noemi, grupează pe agent, întoarce
  sumar + detaliu.
- `services/exercitiu_service.py:864-889` — `assign_comenzi_fara_ind(assignments)`
  upsert în `comenzi_fara_ind_assignments` (SQLite, `UNIQUE(nr_comanda, chain, ship_to)`).

Frontend (SPA):
- `templates/index.html:1171` — entry în sidebar "Analiza Vanzari"
  (`data-view="comenzi_fara_ind"`), afișat și în tree-ul din `line:1293`.
- `templates/index.html:1995` — dispatch `case 'comenzi_fara_ind'` →
  `renderComenzifaraInd(main)`.
- `templates/index.html:7584-7760+` — `renderComenzifaraInd(main)`,
  `_cfiSave(...)`, `_cfiExportAgent(idx)`; nu există `static/js/` dedicat.
- `templates/index.html:7320` — banner "warning" în `Vz la zi` cu click-shortcut.

Definiția **fără IND** (legacy, canonic):
```python
has_ind = bool(ind_val and str(ind_val).strip() not in ('', 'nan', 'None'))
# linia apare in comenzi_fara_ind daca:
#   not has_ind  AND  (is_nefacturat  OR  cant_rest > 0)
```

Tabela de assignments (SQLite legacy, auto-created on first call):
```sql
CREATE TABLE comenzi_fara_ind_assignments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nr_comanda TEXT NOT NULL,
  chain      TEXT NOT NULL,
  ship_to    TEXT NOT NULL,
  agent      TEXT NOT NULL DEFAULT '',
  notes      TEXT NOT NULL DEFAULT '',
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(nr_comanda, chain, ship_to)
)
```

## 3. SaaS — mapare pe `RawOrder`

Model existent în `backend/app/modules/orders/models.py`:

| Camp legacy (JSON)        | SaaS `RawOrder`          | Notă                                           |
|---------------------------|--------------------------|------------------------------------------------|
| `chain`                   | `chain`                  | string, ex. `DEDEMAN`, `LEROY`.               |
| `client`                  | `client` (+ `client_code`)| `client_raw` în response.                     |
| `nr_comanda`              | `nr_comanda`             | nullable.                                      |
| `ship_to`                 | `ship_to`                | raw name magazin.                              |
| `cod_art` / `descriere`   | `product_code` / `product_name` | — linia de produs.                      |
| `tip2`                    | **lipsă**                | → nu e în model; poate merge în `category_code` sau adăugat ulterior. |
| `cant_rest`               | `remaining_quantity`     | —                                              |
| `suma_rest`               | `remaining_amount`       | pre-calculat la import, conform regulilor.     |
| `data_livrare`            | `data_livrare`           | string (ex. `YYYY-MM-DD` sau format RO).       |
| `status`                  | `status`                 | `NELIVRAT` / `NEFACTURAT`.                     |
| `ind` / `has_ind`         | `ind` / `has_ind`        | `has_ind = False` → candidat `comenzi_fara_ind`.|
| —                         | `source`                 | filtru: `source='adp'`.                        |
| —                         | `store_id` / `agent_id`  | backfill după import (agent-ul rezolvat).      |
| —                         | `report_date`            | snapshot-ul folosit pentru "Actualizat".      |

**Criteriu SQL canonic** pentru "fără IND" în SaaS:

```sql
WHERE raw_orders.tenant_id = :tenant
  AND raw_orders.source     = 'adp'
  AND raw_orders.has_ind    = FALSE
  AND raw_orders.report_date = :report_date   -- latest snapshot
  AND (
        raw_orders.status IN ('NEFACTURAT','NEFACTURARE')
     OR raw_orders.remaining_quantity > 0
      )
```

Dacă `report_date` nu e dat, se folosește `MAX(report_date) WHERE source='adp'`.

Pentru manual assignments SaaS avem **două opțiuni**:
- A (recomandat): tabel nou `order_ind_assignments` (tenant-aware) cu UNIQUE
  `(tenant_id, nr_comanda, chain, ship_to)` + FK `agent_id UUID` și `notes`.
- B: refolosește backfill-ul de `agent_id` pe `RawOrder` + un flag `manual=true`.
  Dezavantaj: se pierde la următorul re-import (cache-ul legacy avea aceeași
  problemă, rezolvată prin overlay pe cheie — de aici varianta A e mai curată).

## 4. Contract API propus

### 4.1 `GET /api/comenzi-fara-ind`

Query params (toate opționale):
- `scope` — `adp` (default/only acceptat pentru moment; SIKA/SIKADP → 400).
- `report_date` — ISO `YYYY-MM-DD`; dacă lipsește → ultimul snapshot ADP.
- `agent_id` — UUID; dacă e setat, filtrează pe un singur agent (rolul `agent`
  îl primește automat din tenant context).
- `include_assigned` — bool (default `true`); dacă `false`, întoarce doar
  `Neatribuit` (pt. view-ul manager "ce mi-a rămas de distribuit").
- `sort` — enum: `value_desc` (default), `value_asc`, `agent_asc`,
  `client_asc`, `date_desc`.

Autorizare:
- `admin`, `manager`, `agent`. Role `observator` → 403.
- Scope `sika` / `sikadp` → 400 `{"code": "ind_not_supported"}`.

### 4.2 `POST /api/comenzi-fara-ind/assign`

Body:
```json
{
  "assignments": [
    {
      "nr_comanda": "ADP-12345",
      "chain": "DEDEMAN",
      "ship_to": "DEDEMAN BACAU",
      "agent_id": "uuid-or-null",
      "notes": "De contactat cumpărătorul până vineri"
    }
  ]
}
```

Autorizare: `admin`, `manager` only → altfel 403.
Comportament: upsert pe `(tenant_id, nr_comanda, chain, ship_to)`;
`agent_id = null` = de-assign (revine la auto-resolve din mapping).
Răspuns: `{"ok": true, "saved": <int>}`.

## 5. Shape JSON răspuns — `GET /api/comenzi-fara-ind`

```json
{
  "scope": "adp",
  "report_date": "2026-04-18",
  "cached_at": "2026-04-18T09:12:41Z",
  "month": 4,
  "month_name": "Aprilie",
  "year_curr": 2026,
  "totals": {
    "total_comenzi": 87,
    "total_linii": 312,
    "total_suma": 548921.40,
    "total_cant": 18344.75,
    "neatribuite_comenzi": 12
  },
  "summary_by_agent": [
    {
      "agent_id": null,
      "agent_name": "Neatribuit",
      "nr_comenzi": 12,
      "nr_magazine": 9,
      "total_suma": 84120.10,
      "total_cant": 2015.00
    },
    {
      "agent_id": "b7c1...",
      "agent_name": "Popescu Ion",
      "nr_comenzi": 24,
      "nr_magazine": 18,
      "total_suma": 214002.80,
      "total_cant": 6110.50
    }
  ],
  "orders": [
    {
      "nr_comanda": "ADP-12345",
      "chain": "DEDEMAN",
      "client": "DEDEMAN SRL",
      "ship_to": "DEDEMAN BACAU",
      "store_id": "uuid|null",
      "agent_id": "uuid|null",
      "agent_name": "Popescu Ion",
      "agent_source": "manual | noemi | none",
      "notes": "string",
      "status": "NELIVRAT",
      "data_livrare": "2026-04-22",
      "total_suma": 12401.50,
      "total_cant": 320.00,
      "lines_count": 4,
      "lines": [
        {
          "product_code": "A-0012",
          "product_name": "Adeziv flexibil 25kg",
          "tip2": "ADEZIV",
          "cant_rest": 120.00,
          "suma_rest": 4200.00,
          "status": "NELIVRAT"
        }
      ]
    }
  ],
  "agents_list": [
    {"agent_id": "uuid", "name": "Popescu Ion"}
  ]
}
```

Note:
- `orders` este **deja grupat** pe `(nr_comanda, chain, ship_to)` (legacy o face
  în JS — mai eficient backend).
- `summary_by_agent` păstrează ordinea `Neatribuit` first, apoi desc după
  `total_suma`.
- `agent_source` — nou vs. legacy: util pentru UI (badge "manual" / "auto").

## 6. Coloane tabel + formule

### Sumar pe agenți
| Coloană       | Formulă                                                                |
|---------------|------------------------------------------------------------------------|
| Agent         | `agent_name` (sau `Neatribuit`)                                        |
| Nr. Comenzi   | `COUNT(DISTINCT nr_comanda)` pe bucket                                  |
| Nr. Magazine  | `COUNT(DISTINCT ship_to)`                                               |
| Valoare (RON) | `SUM(remaining_amount)` — pre-calculat la import cu regula NELIVRAT/NEFACTURAT |
| Cantitate     | `SUM(remaining_quantity)`                                               |

### Detaliu comandă (header)
| Coloană       | Formulă                                                                |
|---------------|------------------------------------------------------------------------|
| Chain         | `chain`                                                                 |
| Ship To       | `ship_to`                                                               |
| Nr. Comandă   | `nr_comanda`                                                            |
| Client        | `client` (raw)                                                          |
| Nr. linii     | `COUNT(*)` linii ale comenzii                                           |
| Valoare       | `SUM(remaining_amount)` peste linii                                     |
| Cantitate     | `SUM(remaining_quantity)`                                               |
| Data Livrare  | `data_livrare` (prima linie — consistent la legacy)                     |
| Status        | `status` (prima linie)                                                  |

### Linii produs
| Coloană       | Formulă                                                                |
|---------------|------------------------------------------------------------------------|
| Produs        | `product_name`                                                          |
| Tip           | `tip2` / `category_code` (TBD: trebuie propagat la import)              |
| Cant. Rest.   | `remaining_quantity`                                                    |
| Valoare       | `remaining_amount`                                                      |
| Data Livrare  | `data_livrare`                                                          |
| Status        | `status`                                                                |

Regula `suma_rest` (calculată la import în `raw_orders.remaining_amount`):
```python
if status.upper() in ('NEFACTURAT', 'NEFACTURARE'):
    remaining_amount = amount                      # full
else:  # NELIVRAT
    remaining_amount = (remaining_quantity / quantity) * amount if quantity > 0 else amount
```

Skip la import (nu intră în `raw_orders` pt. "fără IND"):
- `status == 'NELIVRAT' AND remaining_quantity <= 0` — e complet livrat.

## 7. Filtre / sortări

Filtre (query params):
- `agent_id` — UUID (sau `null` pentru `Neatribuit` only).
- `chain` — ex. `DEDEMAN`.
- `status` — `NELIVRAT` / `NEFACTURAT`.
- `search` — substring match pe `nr_comanda`, `client`, `ship_to`, `product_name`.
- `include_assigned` (true/false).

Sortări (`sort`):
- `value_desc` (default) — după `total_suma` desc.
- `value_asc`.
- `agent_asc` — cu `Neatribuit` la final când e `asc`, primul la default.
- `client_asc`.
- `date_desc` — după `data_livrare` desc.

## 8. Acțiuni

1. **Assign agent** (manager+): `POST /api/comenzi-fara-ind/assign` cu
   `agent_id` + `notes`. Server-side invalidează orice cache și întoarce
   `{ok: true, saved}`; clientul re-fetch-uie lista.
2. **De-assign** (manager+): trimite `agent_id: null` pe același endpoint.
3. **Export CSV per agent**: `GET /api/comenzi-fara-ind/export?agent_id=...&format=csv`
   (header identic cu legacy: `Nr Comanda;Client;Chain;Ship To;Produs;Tip;Cant Rest;Valoare Rest;Data Livrare;Status`,
   BOM + `;` separator, filename `Comenzi_fara_IND_{AGENT}_{MONTH}_{YEAR}.csv`).
4. **Export XLS per agent** (opțional, legacy buton "XLS" apelează export CSV
   în realitate — păstrăm doar CSV în v1).
5. **Nu** există edit IND inline legacy — doar atribuire agent + notes.
   (În SaaS putem adăuga ulterior `PATCH /api/raw-orders/{id}` pentru a
   scrie IND-ul manual când agentul îl obține.)

## 9. Diferențe per scope

| Scope    | Are IND? | Endpoint accesibil?                                |
|----------|----------|----------------------------------------------------|
| `adp`    | DA       | DA — flow complet                                   |
| `sika`   | NU       | NU — 400 `ind_not_supported`; view ascuns în sidebar|
| `sikadp` | NU (combinat) | NU — idem                                      |

Company switcher (`ADEPLAST/SIKA/SIKADP`) trebuie să ascundă entry-ul din
sidebar când scope-ul curent nu e `adp` — același pattern ca `raw_sales`
pentru alte view-uri scope-aware.

## 10. TODO / open questions

- `tip2` — nu e în `RawOrder`; la import-ul ADP legacy era `row[15]`.
  Propun adăugare `tip2: Mapped[str | None]` în `RawOrder` sau folosire
  `category_code` dacă e consistent. Nu e blocant pentru v1 (coloana poate fi goală).
- `cached_at` — în legacy vine din `exercitiu_adeplast_cache.updated_at`;
  în SaaS → `MAX(raw_orders.created_at) WHERE report_date = :report_date AND source='adp'`.
- Assignments migrate: dacă se importă istoric din legacy, se poate face
  un script one-shot care citește `comenzi_fara_ind_assignments` (SQLite)
  și inserează în `order_ind_assignments` SaaS.
- Auto-resolve agent: în SaaS e deja `agent_id` pe `RawOrder` (backfill din
  `mapping_service`). Pentru `Neatribuit` bucket înseamnă `agent_id IS NULL`
  **și** lipsa unui override manual.
