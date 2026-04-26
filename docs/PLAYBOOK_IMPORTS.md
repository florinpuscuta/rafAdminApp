# Playbook — Import / Export date

Ghid operațional pentru responsabili de date Adeplast / Sika. Include
formatul așteptat al fișierelor Excel, fluxul end-to-end și remedieri
pentru cazurile de eroare frecvente.

---

## 1. Importuri suportate

| Tip                | Endpoint                                | `batch.source`     | UI                  |
| ------------------ | --------------------------------------- | ------------------ | ------------------- |
| Vânzări Adeplast   | `POST /api/sales/import` (`source=adp`) | `sales_xlsx`       | Vânzări → Importă   |
| Vânzări Sika hist. | `POST /api/sales/import` (`source=sika`) | `sika_xlsx`       | Vânzări → Importă   |
| Vânzări Sika MTD   | `POST /api/sales/import` (`source=sika_mtd`) | `sika_mtd_xlsx` | Vânzări → Importă   |
| Comenzi Adeplast   | `POST /api/orders/import`               | —                  | Comenzi → Importă   |
| Catalog produse    | `POST /api/products/import`             | —                  | Produse → Importă   |
| Prețuri producție  | `POST /api/pret-productie/upload`       | —                  | Costuri → Upload    |

Toate endpoint-urile rulează **sincron** pentru fișiere mici. Pentru
fișiere mari (>10 MB sau >50k rânduri), folosește varianta async:
`POST /api/sales/import/async` → poll `GET /api/sales/import/jobs/{id}`.

---

## 2. Format Excel — Vânzări Adeplast

### Coloane obligatorii

| Coloană logică | Aliasuri header acceptate                                  | Tip      |
| -------------- | ---------------------------------------------------------- | -------- |
| `year`         | `Year`, `An`, `Anul`, `Yr`                                 | int      |
| `month`        | `Month`, `Luna`, `Lun`, `Mth`                              | int      |
| `client`       | `Client`, `Firma`, `Company`, `Customer`                   | string   |
| `amount`       | `Amount`, `Sales`, `Vanzari`, `Valoare`, `Net Sales`, `Suma` | numeric |

### Coloane opționale (recomandate)

| Coloană logică  | Aliasuri header                                       |
| --------------- | ----------------------------------------------------- |
| `quantity`      | `Quantity`, `Cantitate`, `Qty`, `KG`, `MC`, `Billed Qty` |
| `channel`       | `Channel`, `Canal`, `Target Market`, `Piata`          |
| `product_code`  | `Product Code`, `Cod Articol`, `SKU`, `Material`      |
| `product_name`  | `Product Name`, `Descriere`, `Denumire`, `Material Desc` |
| `category_code` | `Category Code`, `Product Category`, `Cod Categorie Articol` |
| `agent`         | `Agent`, `Responsabil`, `Sales Rep`, `Reprezentant`   |
| `ship_to`       | `Ship To`, `Punct de lucru`, `Punct Lucru`            |

### Reguli

- **Header auto-detect** pe primele 20 rânduri — fișierele de la providers
  pot avea titluri / rânduri goale înainte de tabelul real.
- **Diacritice** și **majuscule/minuscule** sunt normalizate. `Cantităţi`,
  `cantităţi`, `Cantitati` se mapează la fel.
- **`channel`** trebuie să fie `KA` pentru clienții Key Account
  (Dedeman, Bricostore, Leroy Merlin, Hornbach, Altex, Praktiker, Puskin).
  Restul pot fi orice (`retail`, `dist`, etc.).
- **`amount`** poate fi negativ pentru storno-uri / corecții.

### Sheet-ul `Alocare` (opțional, doar Adeplast)

Pe lângă sheet-ul principal cu vânzări, fișierul ADP poate conține un
sheet numit `Alocare` cu coloanele: `Client`, `Agent`, `Punct Lucru`.
Importer-ul:

1. Creează magazinele canonice lipsă pentru fiecare combinație
   `(Punct Lucru, Client)`.
2. Adaugă alias-uri `client → store` și `agent → canonic`.
3. Persistă mapping-uri `agent_store_assignments`.

Lipsa sheet-ului `Alocare` nu blochează importul — doar canonicalizarea
rămâne manuală (vezi §6).

---

## 3. Format Excel — Vânzări Sika

Două variante. **Diferență cheie:** scope-uri diferite în `batch.source`,
care determină comportamentul de dedup.

### `source=sika` — istoric Sika (`sika_xlsx`)

Fișier emis de Sika, lunile finalizate. Folosit pentru istoric pe ani
întregi. Header acceptat similar cu ADP, plus aliasuri Sika-specifice.

### `source=sika_mtd` — month-to-date (`sika_mtd_xlsx`)

Fișier intermediar pentru luna curentă (date parțiale). Ține de luna
care se construiește încă. La consolidare, **MTD prevalează asupra
istoric-ului Sika** pentru lunile suprapuse — un singur source contează
per `(year, month)`.

### Reguli specifice

- Sika nu are sheet `Alocare` — canonicalizarea agenților se face manual
  (Settings → Agent aliases) sau prin SAM (Settings → SAM mappings).
- Re-importul aceleiași luni Sika rescrie complet datele pentru acel
  source (vezi §4).

---

## 4. Comportament re-import (`full_reload`)

Endpoint-ul `/api/sales/import` acceptă query param `?full_reload=true|false`
(default `false`):

| Mod              | Ce se șterge înainte de insert                            |
| ---------------- | --------------------------------------------------------- |
| `full_reload=false` (default) | Doar rânduri din `(year, month)` care apar în noul fișier, **scoped pe `batch.source`**. Astfel un re-import ADP NU șterge datele Sika. |
| `full_reload=true`            | Tot istoricul `batch.source` curent. **Periculos** — folosit doar la migrări de format / reseturi controlate. |

Pentru Sika: ștergerea afectează **ambele** source-uri (`sika_xlsx` +
`sika_mtd_xlsx`) pentru lunile acoperite de noul fișier — astfel MTD și
istoric nu rămân în conflict.

---

## 5. Cum verifici un import

După import, UI-ul afișează un panou cu:

- `inserted`: rânduri RawSale create
- `skipped`: rânduri respinse (cu erori în câmpul `errors[]`)
- `deleted_before_insert`: șterse pentru re-load
- `unmapped_clients`, `unmapped_agents`, `unmapped_products`: rânduri
  care n-au fost canonicalizate (string brut păstrat)
- `months_affected`: lista `["2026-01", "2026-02", ...]`

### Sanity check (prin API)

```bash
# Total general
curl -H "Authorization: Bearer $TOKEN" \
  "https://krossdash.ro/api/dashboard/overview"

# Detalii pe batch
curl -H "Authorization: Bearer $TOKEN" \
  "https://krossdash.ro/api/sales/batches" | jq '.[0]'
```

### Sanity check (prin UI)

1. Vânzări → Listare → filtrează pe luna importată → verifică totalul.
2. Consolidat → KA → compară Y1 vs Y2 (anomalii vizibile imediat).
3. Mapări → verifică `unmapped_clients` (clienți noi neasignați).

---

## 6. Canonicalizare — ce faci cu `unmapped_*`

Importul nu blochează când un client/agent/produs nu e canonic — păstrează
string-ul brut și raportează count-ul. Ulterior:

### Clienți → magazine canonice

Settings → **Mapări → Magazine** → vezi clienții fără mapare. Pentru
fiecare:
- **Crează magazin nou** dacă e o locație fizică distinctă (auto-creează
  alias-ul).
- **Adaugă alias** la un magazin existent (ex. variante de scriere).

### Agenți

Settings → **Mapări → Agenți** → asociază alias-urile vechi cu agentul
canonical (sau crează agent nou).

### Produse

Settings → **Produse → Aliasuri** — la fel, alias → produs canonic.

### Re-rezolvare (backfill)

După ce adaugi mapări, FK-urile pe `raw_sales` se completează automat
prin `POST /api/sales/backfill` (rulat automat după fiecare import).
Pentru re-rezolvare manuală: butonul **Re-resolve** din pagina de
Mapări.

---

## 7. Export

### Excel — vânzări brute

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -o sales_export.csv \
  "https://krossdash.ro/api/sales/export?year=2026&month=4"
```

Sau prin UI: Vânzări → Export CSV (filtrul curent aplicat).

### Rapoarte Word

`POST /api/reports/word/monthly` — generează DOCX cu charts. UI:
Rapoarte → Lunar → buton "Generează".

### Backup DB (admin)

Vezi `DEPLOY.md` §6 pentru `pg_dump` programat. Backup automat S3 e pe
roadmap (pasul 6 din planul "10/10").

---

## 8. Troubleshooting

| Simptom                                 | Cauză probabilă                          | Remediu                                                  |
| --------------------------------------- | ---------------------------------------- | -------------------------------------------------------- |
| `parse_error` la upload                 | Header lipsește sau e ilizibil           | Verifică prin §2 — primele 20 rânduri trebuie să conțină coloanele obligatorii. |
| `inserted=0`, `skipped=N`               | Rânduri cu `amount` invalid / `month` neacceptat | Inspectează `errors[]` din response. |
| Sume nu se potrivesc cu raportul Sika   | `sika_mtd` peste `sika` neaplicat        | Re-import Sika MTD — dedup se face automat la consolidat. |
| Lipsesc clienți după import             | `Alocare` absent / clienți noi           | Adaugă manual în Mapări → Magazine. |
| `Consolidat` arată x2 magazine la SIKADP | Bug rezolvat (commit `1cbf91b`)         | Restart backend după pull. |
| Cache stale după import                 | Auto-invalidare nu a rulat               | Restart backend; sau `POST /api/admin/cache/invalidate?tenant=...` (TBD). |

---

## 9. Limite & restricții

- **Mărime fișier**: max 100 MB (limită Caddy + slowapi). Peste — folosește
  endpoint-ul async și split-uiește pe luni.
- **Rate limit**: 10 importuri / oră / tenant (slowapi).
- **Retention**: `raw_sales` păstrează tot istoricul. `import_batches` la fel.
  Pentru curățare programată, vezi `app.core.cleanup`.

---

**Versiune**: 1.0 (2026-04-26)
**Owner**: Florin Pușcuța
