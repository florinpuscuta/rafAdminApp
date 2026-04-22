"""Data layer pentru raportul lunar.

Pattern: queries deterministe din DB, agregări calculate înainte să plece la LLM.
Structura replică rapoartele RAF Consulting (Adeplast / Sika / Consolidat).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ─────────────────────────────────────────────────────────────────────────
# Shared dataclasses
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class YoY:
    """Valoare curentă + an anterior + diferență calculată."""
    current: float = 0.0
    prev: float = 0.0

    @property
    def diff(self) -> float:
        return self.current - self.prev

    @property
    def pct(self) -> float | None:
        if self.prev <= 0:
            return None
        return (self.diff / self.prev) * 100


@dataclass
class Row:
    label: str
    cur: float = 0.0
    prev: float = 0.0
    qty_cur: float = 0.0
    qty_prev: float = 0.0

    @property
    def diff(self) -> float:
        return self.cur - self.prev

    @property
    def pct(self) -> float | None:
        if self.prev <= 0:
            return None
        return ((self.cur - self.prev) / self.prev) * 100


@dataclass
class BrandDossier:
    brand: str
    year: int
    month: int
    prev_year: int
    amount: YoY
    quantity: YoY
    amount_ytd: YoY
    quantity_ytd: YoY
    top_clients: list[Row] = field(default_factory=list)
    top_categories: list[Row] = field(default_factory=list)
    top_products: list["ProductRow"] = field(default_factory=list)


@dataclass
class ZoneRow:
    zone: str
    stores: int
    amount_current: float
    amount_prev: float

    @property
    def diff(self) -> float:
        return self.amount_current - self.amount_prev

    @property
    def pct(self) -> float | None:
        if self.amount_prev <= 0:
            return None
        return (self.diff / self.amount_prev) * 100


@dataclass
class ZoneDossier:
    year: int
    month: int
    prev_year: int
    zones: list[ZoneRow]

    @property
    def total_current(self) -> float:
        return sum(z.amount_current for z in self.zones)

    @property
    def total_prev(self) -> float:
        return sum(z.amount_prev for z in self.zones)

    @property
    def total_diff(self) -> float:
        return self.total_current - self.total_prev

    @property
    def total_pct(self) -> float | None:
        if self.total_prev <= 0:
            return None
        return (self.total_diff / self.total_prev) * 100


@dataclass
class MarcaPrivataDossier:
    """Doar pentru Adeplast — split Adeplast vs Marca Privată în cadrul Adeplast."""
    year: int
    month: int
    prev_year: int
    adeplast: YoY
    marca_privata: YoY
    categories_pl: list[Row] = field(default_factory=list)


@dataclass
class PriceRow:
    store: str
    group: str
    product_adp: str
    price_adp: float
    price_sika: float | None
    competitors: list[tuple[str, float]]  # (brand, price)

    @property
    def avg_competitor(self) -> float | None:
        if not self.competitors:
            return None
        return sum(p for _, p in self.competitors) / len(self.competitors)

    @property
    def advantage_pct(self) -> float | None:
        avg = self.avg_competitor
        if avg is None or avg <= 0:
            return None
        return ((self.price_adp - avg) / avg) * 100


@dataclass
class PriceGridLine:
    """Un rând din price_grid: un produs al brand-ului ancoră +
    prețurile corespondente la competitori/marci private."""
    store: str
    row_num: int
    group: str
    # brand → {"prod": str|None, "pret": float|None}
    brand_prices: dict[str, dict[str, object]]


@dataclass
class StorePriceTable:
    """Tabel cu toate rândurile dintr-un magazin pentru un company anchor."""
    store: str
    anchor_brand: str  # 'ADEPLAST' sau 'Sika'
    # Coloane ordonate: întâi anchor, apoi competitorii
    columns: list[str]
    rows: list[PriceGridLine]


@dataclass
class PriceDossier:
    rows: list[PriceRow]
    stores_covered: list[str]
    avg_advantage_pct: float | None
    adeplast_tables: list[StorePriceTable]  # câte unul per magazin
    sika_tables: list[StorePriceTable]


@dataclass
class ProductRow:
    code: str
    name: str
    category: str | None
    cur: float
    prev: float

    @property
    def diff(self) -> float:
        return self.cur - self.prev

    @property
    def pct(self) -> float | None:
        if self.prev <= 0:
            return None
        return ((self.cur - self.prev) / self.prev) * 100


@dataclass
class MarketingPhoto:
    """Poză embedded în raport (bytes + meta)."""
    caption: str
    png_bytes: bytes


@dataclass
class MarketingDossier:
    catalog_folder_name: str | None
    catalog_photos: list[MarketingPhoto]
    panouri_photos: list[MarketingPhoto]
    magazine_photos: list[MarketingPhoto]
    panouri_count: int
    magazine_count: int
    catalog_count: int


@dataclass
class FullDossier:
    """Un singur obiect cu tot ce intră în raport."""
    year: int
    month: int
    prev_year: int
    total: YoY
    total_ytd: YoY
    adeplast: BrandDossier
    sika: BrandDossier
    marca_privata: MarcaPrivataDossier
    consolidated_top_clients: list[Row]
    zones: ZoneDossier
    monthly_evolution: list[tuple[int, float, float]]  # (month, curr, prev)
    prices: PriceDossier
    marketing: MarketingDossier


# ─────────────────────────────────────────────────────────────────────────
# Query helpers
# ─────────────────────────────────────────────────────────────────────────

async def _brand_yoy(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int, brand: str,
    ytd: bool = False,
) -> YoY:
    if ytd:
        where_month = "rs.month BETWEEN 1 AND :m"
    else:
        where_month = "rs.month = :m"
    rows = (await session.execute(
        text(f"""
            SELECT rs.year, SUM(rs.amount)::float AS amt, SUM(COALESCE(rs.quantity, 0))::float AS qty
            FROM raw_sales rs
            LEFT JOIN products p ON p.id = rs.product_id
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND {where_month}
              AND rs.year IN (:y, :prev)
              AND (
                CASE
                  WHEN :brand = 'Adeplast' THEN p.brand IN ('Adeplast', 'Marca Privata')
                  ELSE p.brand = :brand
                END
              )
            GROUP BY rs.year
        """),
        {"t": str(tenant_id), "y": year, "prev": year - 1, "m": month, "brand": brand},
    )).all()
    by_year = {r[0]: (float(r[1] or 0), float(r[2] or 0)) for r in rows}
    cur_amt, cur_qty = by_year.get(year, (0.0, 0.0))
    prev_amt, prev_qty = by_year.get(year - 1, (0.0, 0.0))
    return YoY(current=cur_amt, prev=prev_amt)


async def _brand_qty_yoy(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int, brand: str, ytd: bool = False,
) -> YoY:
    if ytd:
        where_month = "rs.month BETWEEN 1 AND :m"
    else:
        where_month = "rs.month = :m"
    rows = (await session.execute(
        text(f"""
            SELECT rs.year, SUM(COALESCE(rs.quantity, 0))::float AS qty
            FROM raw_sales rs
            LEFT JOIN products p ON p.id = rs.product_id
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND {where_month}
              AND rs.year IN (:y, :prev)
              AND (
                CASE
                  WHEN :brand = 'Adeplast' THEN p.brand IN ('Adeplast', 'Marca Privata')
                  ELSE p.brand = :brand
                END
              )
            GROUP BY rs.year
        """),
        {"t": str(tenant_id), "y": year, "prev": year - 1, "m": month, "brand": brand},
    )).all()
    by_year = {r[0]: float(r[1] or 0) for r in rows}
    return YoY(current=by_year.get(year, 0.0), prev=by_year.get(year - 1, 0.0))


async def _top_clients(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int, brand: str | None = None, limit: int = 10,
) -> list[Row]:
    """Top clienți după chain (retailerul).

    brand=None → toate brandurile (consolidat).
    brand='Adeplast' → include Adeplast + Marca Privată.
    """
    brand_filter = ""
    params: dict = {
        "t": str(tenant_id), "y": year, "prev": year - 1,
        "m": month, "lim": limit,
    }
    if brand == "Adeplast":
        brand_filter = "AND p.brand IN ('Adeplast', 'Marca Privata')"
    elif brand:
        brand_filter = "AND p.brand = :brand"
        params["brand"] = brand

    rows = (await session.execute(
        text(f"""
            WITH agg AS (
              SELECT
                COALESCE(NULLIF(TRIM(s.chain), ''), 'FĂRĂ LANȚ') AS chain,
                SUM(CASE WHEN rs.year = :y THEN rs.amount ELSE 0 END)::float AS cur,
                SUM(CASE WHEN rs.year = :prev THEN rs.amount ELSE 0 END)::float AS prev
              FROM raw_sales rs
              JOIN stores s ON s.id = rs.store_id
              LEFT JOIN products p ON p.id = rs.product_id
              WHERE rs.tenant_id = :t
                AND UPPER(rs.channel) = 'KA'
                AND rs.month = :m
                AND rs.year IN (:y, :prev)
                {brand_filter}
              GROUP BY chain
              HAVING SUM(rs.amount) > 0
            )
            SELECT chain, cur, prev FROM agg
            ORDER BY cur DESC NULLS LAST
            LIMIT :lim
        """),
        params,
    )).all()
    return [Row(label=r[0], cur=float(r[1] or 0), prev=float(r[2] or 0)) for r in rows]


async def _top_categories(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int, brand: str,
    limit: int = 10,
) -> list[Row]:
    params: dict = {
        "t": str(tenant_id), "y": year, "prev": year - 1,
        "m": month, "lim": limit,
    }
    brand_filter = "AND p.brand IN ('Adeplast', 'Marca Privata')" if brand == "Adeplast" else "AND p.brand = :brand"
    if brand != "Adeplast":
        params["brand"] = brand
    rows = (await session.execute(
        text(f"""
            SELECT
              COALESCE(NULLIF(TRIM(p.category), ''), 'ALTELE') AS cat,
              SUM(CASE WHEN rs.year = :y THEN rs.amount ELSE 0 END)::float AS cur,
              SUM(CASE WHEN rs.year = :prev THEN rs.amount ELSE 0 END)::float AS prev
            FROM raw_sales rs
            LEFT JOIN products p ON p.id = rs.product_id
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND rs.month = :m
              AND rs.year IN (:y, :prev)
              {brand_filter}
            GROUP BY cat
            HAVING SUM(rs.amount) > 0
            ORDER BY cur DESC NULLS LAST
            LIMIT :lim
        """),
        params,
    )).all()
    return [Row(label=r[0], cur=float(r[1] or 0), prev=float(r[2] or 0)) for r in rows]


async def _top_products(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int, brand: str, limit: int = 15,
) -> list["ProductRow"]:
    """Top N produse pentru un brand dat, pe baza vânzărilor din raw_sales."""
    brand_filter = (
        "p.brand IN ('Adeplast', 'Marca Privata')" if brand == "Adeplast"
        else "p.brand = :brand"
    )
    params: dict = {"t": str(tenant_id), "y": year, "prev": year - 1,
                    "m": month, "lim": limit}
    if brand != "Adeplast":
        params["brand"] = brand

    rows = (await session.execute(
        text(f"""
            SELECT
              COALESCE(p.code, '—') AS code,
              COALESCE(NULLIF(TRIM(p.name), ''), rs.product_name, '—') AS name,
              COALESCE(NULLIF(TRIM(p.category), ''), 'ALTELE') AS cat,
              SUM(CASE WHEN rs.year = :y THEN rs.amount ELSE 0 END)::float AS cur,
              SUM(CASE WHEN rs.year = :prev THEN rs.amount ELSE 0 END)::float AS prev
            FROM raw_sales rs
            LEFT JOIN products p ON p.id = rs.product_id
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND rs.month = :m
              AND rs.year IN (:y, :prev)
              AND {brand_filter}
            GROUP BY p.code, p.name, rs.product_name, p.category
            HAVING SUM(CASE WHEN rs.year = :y THEN rs.amount ELSE 0 END) > 0
            ORDER BY cur DESC NULLS LAST
            LIMIT :lim
        """),
        params,
    )).all()
    return [
        ProductRow(code=r[0] or "—", name=r[1] or "—", category=r[2],
                   cur=float(r[3] or 0), prev=float(r[4] or 0))
        for r in rows
    ]


async def _marca_privata(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> MarcaPrivataDossier:
    prev_year = year - 1
    rows = (await session.execute(
        text("""
            SELECT p.brand, rs.year, SUM(rs.amount)::float
            FROM raw_sales rs
            LEFT JOIN products p ON p.id = rs.product_id
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND rs.month = :m
              AND rs.year IN (:y, :prev)
              AND p.brand IN ('Adeplast', 'Marca Privata')
            GROUP BY p.brand, rs.year
        """),
        {"t": str(tenant_id), "y": year, "prev": prev_year, "m": month},
    )).all()
    adp = YoY(); pl = YoY()
    for brand, yr, amt in rows:
        a = float(amt or 0)
        target = adp if brand == "Adeplast" else pl
        if yr == year: target.current = a
        elif yr == prev_year: target.prev = a

    cat_rows = (await session.execute(
        text("""
            SELECT
              COALESCE(NULLIF(TRIM(p.category), ''), 'ALTELE') AS cat,
              SUM(CASE WHEN rs.year = :y THEN rs.amount ELSE 0 END)::float AS cur,
              SUM(CASE WHEN rs.year = :prev THEN rs.amount ELSE 0 END)::float AS prev
            FROM raw_sales rs
            LEFT JOIN products p ON p.id = rs.product_id
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND rs.month = :m
              AND rs.year IN (:y, :prev)
              AND p.brand = 'Marca Privata'
            GROUP BY cat
            HAVING SUM(rs.amount) > 0
            ORDER BY cur DESC NULLS LAST
            LIMIT 10
        """),
        {"t": str(tenant_id), "y": year, "prev": prev_year, "m": month},
    )).all()
    cats = [Row(label=r[0], cur=float(r[1] or 0), prev=float(r[2] or 0)) for r in cat_rows]
    return MarcaPrivataDossier(
        year=year, month=month, prev_year=prev_year,
        adeplast=adp, marca_privata=pl, categories_pl=cats,
    )


async def _monthly_evolution(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, up_to_month: int,
) -> list[tuple[int, float, float]]:
    """Pentru fiecare lună 1..up_to_month: (month, curr_year, prev_year)."""
    rows = (await session.execute(
        text("""
            SELECT rs.month, rs.year, SUM(rs.amount)::float
            FROM raw_sales rs
            WHERE rs.tenant_id = :t
              AND UPPER(rs.channel) = 'KA'
              AND rs.year IN (:y, :prev)
              AND rs.month BETWEEN 1 AND :m
            GROUP BY rs.month, rs.year
        """),
        {"t": str(tenant_id), "y": year, "prev": year - 1, "m": up_to_month},
    )).all()
    by: dict[int, dict[int, float]] = {}
    for m, yr, amt in rows:
        by.setdefault(m, {})[yr] = float(amt or 0)
    out: list[tuple[int, float, float]] = []
    for m in range(1, up_to_month + 1):
        rec = by.get(m, {})
        out.append((m, rec.get(year, 0.0), rec.get(year - 1, 0.0)))
    return out


async def _grid_table_for_company(
    session: AsyncSession, tenant_id: UUID,
    *, company: str, anchor_brand: str,
) -> list[StorePriceTable]:
    """Construiește tabele per magazin pentru un company (adeplast / sika).

    Returnează o listă de StorePriceTable — câte unul per magazin.
    """
    rows_db = (await session.execute(
        text("""
            SELECT store, row_num, group_label, brand_data
            FROM price_grid
            WHERE tenant_id = :t AND company = :c
            ORDER BY store, row_num::int
        """),
        {"t": str(tenant_id), "c": company},
    )).all()

    # Grupare pe magazin
    by_store: dict[str, list[tuple[int, str, dict]]] = {}
    for store, rn, group, bd in rows_db:
        if not store:
            continue
        try:
            rn_i = int(rn) if rn is not None else 0
        except (TypeError, ValueError):
            rn_i = 0
        by_store.setdefault(store, []).append((rn_i, group or "", bd or {}))

    tables: list[StorePriceTable] = []
    for store, triples in sorted(by_store.items()):
        # Colectez ordinea coloanelor — primele sunt cele care apar cel mai des
        col_counts: dict[str, int] = {}
        for _, _, bd in triples:
            for k in bd.keys():
                col_counts[k] = col_counts.get(k, 0) + 1
        # Ordonează: anchor_brand primul, apoi ceilalți după frecvență
        ordered = [anchor_brand] if anchor_brand in col_counts else []
        ordered += [
            c for c, _ in sorted(col_counts.items(), key=lambda x: -x[1])
            if c != anchor_brand
        ]

        grid_lines: list[PriceGridLine] = []
        for rn, group, bd in sorted(triples, key=lambda x: x[0]):
            # Ignoră rânduri fără niciun preț
            has_any = False
            normalised: dict[str, dict[str, object]] = {}
            for brand in ordered:
                obj = bd.get(brand) or {}
                if not isinstance(obj, dict):
                    normalised[brand] = {"prod": None, "pret": None}
                    continue
                prod = obj.get("prod")
                try:
                    pret = float(obj.get("pret")) if obj.get("pret") is not None else None
                except (TypeError, ValueError):
                    pret = None
                if pret is not None and pret > 0:
                    has_any = True
                normalised[brand] = {"prod": prod, "pret": pret}
            if not has_any:
                continue
            grid_lines.append(PriceGridLine(
                store=store, row_num=rn, group=group, brand_prices=normalised,
            ))

        if grid_lines:
            tables.append(StorePriceTable(
                store=store,
                anchor_brand=anchor_brand,
                columns=ordered,
                rows=grid_lines,
            ))
    return tables


async def _price_dossier(
    session: AsyncSession, tenant_id: UUID,
) -> PriceDossier:
    """Scoate top 20 rânduri comparative + tabele full per magazin (Adeplast + Sika)."""
    rows_db = (await session.execute(
        text("""
            SELECT store, group_label, brand_data, row_num
            FROM price_grid
            WHERE tenant_id = :t
              AND company = 'adeplast'
              AND brand_data ? 'ADEPLAST'
              AND (brand_data->'ADEPLAST'->>'pret') IS NOT NULL
            ORDER BY store, row_num::int
            LIMIT 40
        """),
        {"t": str(tenant_id)},
    )).all()

    out: list[PriceRow] = []
    stores: set[str] = set()
    advantages: list[float] = []
    for store, group, bd, _rn in rows_db:
        bd = bd or {}
        adp_obj = bd.get("ADEPLAST") or {}
        sika_obj = bd.get("Sika") or {}
        try:
            price_adp = float(adp_obj.get("pret") or 0)
        except (TypeError, ValueError):
            continue
        if price_adp <= 0:
            continue
        try:
            price_sika = float(sika_obj.get("pret")) if sika_obj.get("pret") else None
        except (TypeError, ValueError):
            price_sika = None

        competitors: list[tuple[str, float]] = []
        for brand, obj in bd.items():
            if brand in ("ADEPLAST", "Sika", "Marci poprii"):
                continue
            if not isinstance(obj, dict):
                continue
            try:
                p = float(obj.get("pret") or 0)
            except (TypeError, ValueError):
                continue
            if p > 0:
                competitors.append((brand, p))

        if not competitors:
            continue

        pr = PriceRow(
            store=store or "—",
            group=group or "",
            product_adp=str(adp_obj.get("prod") or ""),
            price_adp=price_adp,
            price_sika=price_sika,
            competitors=competitors,
        )
        out.append(pr)
        stores.add(pr.store)
        if pr.advantage_pct is not None:
            advantages.append(pr.advantage_pct)

    avg_adv = sum(advantages) / len(advantages) if advantages else None

    adeplast_tables = await _grid_table_for_company(
        session, tenant_id, company="adeplast", anchor_brand="ADEPLAST",
    )
    sika_tables = await _grid_table_for_company(
        session, tenant_id, company="sika", anchor_brand="Sika",
    )

    return PriceDossier(
        rows=out[:20],
        stores_covered=sorted(stores),
        avg_advantage_pct=avg_adv,
        adeplast_tables=adeplast_tables,
        sika_tables=sika_tables,
    )


async def _marketing_dossier(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int, max_photos_per_section: int = 4,
) -> MarketingDossier:
    """Adună poze aprobate din gallery (catalog / panouri / magazine)."""
    # Import-uri locale — storage necesar doar aici
    try:
        from app.core import storage
    except ImportError:  # pragma: no cover
        storage = None  # type: ignore[assignment]

    # Gallery folder pentru luna curentă — încearcă să potrivească după nume
    # (ex: "Aprilie 2026", "aprilie", "2026_04", ... )
    month_ro = MONTHS_RO[month] if 1 <= month <= 12 else ""
    month_patterns = [
        f"{month_ro} {year}", f"{month_ro}", f"{year}_{month:02d}",
        f"{month:02d}/{year}", f"{year}-{month:02d}",
    ]

    # 1. Total counts
    counts = (await session.execute(
        text("""
            SELECT gf.type, count(gp.id)
            FROM gallery_folders gf
            LEFT JOIN gallery_photos gp ON gp.folder_id = gf.id
              AND gp.approval_status = 'approved'
            WHERE gf.tenant_id = :t
            GROUP BY gf.type
        """),
        {"t": str(tenant_id)},
    )).all()
    by_type = {r[0]: int(r[1] or 0) for r in counts}

    # 2. Catalog — doar folderul lunii curente (sau cel mai apropiat)
    catalog_rows = (await session.execute(
        text("""
            SELECT gp.object_key, gp.filename, gf.name
            FROM gallery_photos gp
            JOIN gallery_folders gf ON gf.id = gp.folder_id
            WHERE gp.tenant_id = :t
              AND gf.type = 'catalog'
              AND gp.approval_status = 'approved'
            ORDER BY gp.uploaded_at DESC
        """),
        {"t": str(tenant_id)},
    )).all()

    catalog_folder = None
    catalog_photos: list[MarketingPhoto] = []
    # Preferă folderele care conțin pattern-ul lunii
    for key, fname, folder_name in catalog_rows:
        if any(p.lower() in (folder_name or "").lower() for p in month_patterns):
            catalog_folder = folder_name
            if storage and len(catalog_photos) < max_photos_per_section:
                try:
                    data, _ct = storage.get_object_stream(key)
                    catalog_photos.append(MarketingPhoto(
                        caption=f"Catalog — {folder_name} · {fname}",
                        png_bytes=data,
                    ))
                except Exception:
                    continue

    # 3. Panouri — poze recente aleatorii
    panouri_rows = (await session.execute(
        text("""
            SELECT gp.object_key, gp.filename, gf.name
            FROM gallery_photos gp
            JOIN gallery_folders gf ON gf.id = gp.folder_id
            WHERE gp.tenant_id = :t
              AND gf.type = 'panouri'
              AND gp.approval_status = 'approved'
            ORDER BY gp.uploaded_at DESC
            LIMIT 20
        """),
        {"t": str(tenant_id)},
    )).all()
    panouri_photos: list[MarketingPhoto] = []
    if storage:
        for key, fname, folder_name in panouri_rows:
            if len(panouri_photos) >= max_photos_per_section:
                break
            try:
                data, _ct = storage.get_object_stream(key)
                panouri_photos.append(MarketingPhoto(
                    caption=f"Panou — {folder_name} · {fname[:40]}",
                    png_bytes=data,
                ))
            except Exception:
                continue

    # 4. Magazine (poze concurență/raft) — poze recente
    magazine_rows = (await session.execute(
        text("""
            SELECT gp.object_key, gp.filename, gf.name
            FROM gallery_photos gp
            JOIN gallery_folders gf ON gf.id = gp.folder_id
            WHERE gp.tenant_id = :t
              AND gf.type IN ('magazine', 'concurenta')
              AND gp.approval_status = 'approved'
            ORDER BY gp.uploaded_at DESC
            LIMIT 20
        """),
        {"t": str(tenant_id)},
    )).all()
    magazine_photos: list[MarketingPhoto] = []
    if storage:
        for key, fname, folder_name in magazine_rows:
            if len(magazine_photos) >= max_photos_per_section:
                break
            try:
                data, _ct = storage.get_object_stream(key)
                magazine_photos.append(MarketingPhoto(
                    caption=f"Magazin — {folder_name} · {fname[:40]}",
                    png_bytes=data,
                ))
            except Exception:
                continue

    return MarketingDossier(
        catalog_folder_name=catalog_folder,
        catalog_photos=catalog_photos,
        panouri_photos=panouri_photos,
        magazine_photos=magazine_photos,
        panouri_count=by_type.get("panouri", 0),
        magazine_count=by_type.get("magazine", 0) + by_type.get("concurenta", 0),
        catalog_count=by_type.get("catalog", 0),
    )


# Needed in _marketing_dossier
MONTHS_RO = [
    "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]


async def zone_dossier(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int,
) -> ZoneDossier:
    """Agregare zone (city) pentru (year, month) + comparație cu (year-1, month)."""
    prev_year = year - 1
    rows = (await session.execute(
        text("""
            SELECT
              COALESCE(NULLIF(TRIM(s.city), ''), 'NECUNOSCUT') AS zone,
              COUNT(DISTINCT rs.store_id) AS stores,
              SUM(CASE WHEN rs.year = :year THEN rs.amount ELSE 0 END)::float AS amount_current,
              SUM(CASE WHEN rs.year = :prev THEN rs.amount ELSE 0 END)::float AS amount_prev
            FROM raw_sales rs
            JOIN stores s ON s.id = rs.store_id
            WHERE rs.tenant_id = :tenant
              AND UPPER(rs.channel) = 'KA'
              AND rs.month = :month
              AND rs.year IN (:year, :prev)
            GROUP BY zone
            HAVING SUM(rs.amount) > 0
            ORDER BY amount_current DESC NULLS LAST
        """),
        {"tenant": str(tenant_id), "year": year, "prev": prev_year, "month": month},
    )).all()

    zones = [
        ZoneRow(
            zone=r[0], stores=int(r[1] or 0),
            amount_current=float(r[2] or 0), amount_prev=float(r[3] or 0),
        )
        for r in rows
    ]
    return ZoneDossier(year=year, month=month, prev_year=prev_year, zones=zones)


# ─────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────

async def full_dossier(
    session: AsyncSession, tenant_id: UUID,
    *, year: int, month: int,
) -> FullDossier:
    """Asamblează TOT dosarul pentru o lună."""
    adeplast_bd = BrandDossier(
        brand="Adeplast", year=year, month=month, prev_year=year - 1,
        amount=await _brand_yoy(session, tenant_id, year=year, month=month, brand="Adeplast"),
        quantity=await _brand_qty_yoy(session, tenant_id, year=year, month=month, brand="Adeplast"),
        amount_ytd=await _brand_yoy(session, tenant_id, year=year, month=month, brand="Adeplast", ytd=True),
        quantity_ytd=await _brand_qty_yoy(session, tenant_id, year=year, month=month, brand="Adeplast", ytd=True),
        top_clients=await _top_clients(session, tenant_id, year=year, month=month, brand="Adeplast", limit=10),
        top_categories=await _top_categories(session, tenant_id, year=year, month=month, brand="Adeplast", limit=10),
        top_products=await _top_products(session, tenant_id, year=year, month=month, brand="Adeplast", limit=15),
    )
    sika_bd = BrandDossier(
        brand="Sika", year=year, month=month, prev_year=year - 1,
        amount=await _brand_yoy(session, tenant_id, year=year, month=month, brand="Sika"),
        quantity=await _brand_qty_yoy(session, tenant_id, year=year, month=month, brand="Sika"),
        amount_ytd=await _brand_yoy(session, tenant_id, year=year, month=month, brand="Sika", ytd=True),
        quantity_ytd=await _brand_qty_yoy(session, tenant_id, year=year, month=month, brand="Sika", ytd=True),
        top_clients=await _top_clients(session, tenant_id, year=year, month=month, brand="Sika", limit=10),
        top_categories=await _top_categories(session, tenant_id, year=year, month=month, brand="Sika", limit=10),
        top_products=await _top_products(session, tenant_id, year=year, month=month, brand="Sika", limit=15),
    )
    mp = await _marca_privata(session, tenant_id, year=year, month=month)
    consolidated_clients = await _top_clients(session, tenant_id, year=year, month=month, brand=None, limit=10)
    zones = await zone_dossier(session, tenant_id, year=year, month=month)
    evolution = await _monthly_evolution(session, tenant_id, year=year, up_to_month=month)
    prices = await _price_dossier(session, tenant_id)
    marketing = await _marketing_dossier(session, tenant_id, year=year, month=month)

    total = YoY(
        current=adeplast_bd.amount.current + sika_bd.amount.current,
        prev=adeplast_bd.amount.prev + sika_bd.amount.prev,
    )
    total_ytd = YoY(
        current=adeplast_bd.amount_ytd.current + sika_bd.amount_ytd.current,
        prev=adeplast_bd.amount_ytd.prev + sika_bd.amount_ytd.prev,
    )

    return FullDossier(
        year=year, month=month, prev_year=year - 1,
        total=total, total_ytd=total_ytd,
        adeplast=adeplast_bd, sika=sika_bd,
        marca_privata=mp,
        consolidated_top_clients=consolidated_clients,
        zones=zones,
        monthly_evolution=evolution,
        prices=prices,
        marketing=marketing,
    )
