import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { getArboreProduse } from "./api";
import type {
  ArboreProduseResponse, TreeBrand, TreeCategory, TreeProduct, TreeSubgroup,
} from "./types";

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

const MONTH_ABBR = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];

function toNum(v: string | null | undefined): number {
  if (v == null) return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtRo(v: string | number | null | undefined): string {
  const n = typeof v === "number" ? v : toNum(v);
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

function fmtPrice(v: string | null | undefined): string {
  const n = toNum(v);
  if (!Number.isFinite(n) || n === 0) return "—";
  return n.toLocaleString("ro-RO", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

function pctChange(curr: string | number | null | undefined,
                   prev: string | number | null | undefined): number | null {
  const c = typeof curr === "number" ? curr : toNum(curr);
  const p = typeof prev === "number" ? prev : toNum(prev);
  if (p === 0) return null;
  return ((c - p) / p) * 100;
}

function DiffPill({ pct }: { pct: number | null }) {
  if (pct == null) {
    return <span style={{ fontSize: 11, color: "var(--fg-muted,#999)" }}>—</span>;
  }
  const positive = pct > 0;
  const bg = positive ? "#16a34a" : pct < 0 ? "#dc2626" : "#6b7280";
  const sign = positive ? "+" : "";
  return (
    <span style={{
      display: "inline-block",
      padding: "1px 6px",
      fontSize: 11,
      fontWeight: 700,
      color: "#fff",
      background: bg,
      borderRadius: 3,
      fontVariantNumeric: "tabular-nums",
    }}>
      {sign}{pct.toFixed(1)}%
    </span>
  );
}

function scopeFromCompany(c: "adeplast" | "sika" | "sikadp"): string {
  return c === "adeplast" ? "adp" : c;
}

function brandColor(b: TreeBrand): string {
  if (b.isPrivateLabel) return "#a855f7";            // violet
  const n = b.name.toLowerCase();
  if (n.includes("adeplast")) return "#22c55e";      // green
  if (n.includes("sika")) return "#eab308";          // yellow
  return "#3b82f6";                                   // blue default
}

type MonthMode = "ytd" | "all" | "custom";

export default function ArboreProdusePage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const toast = useToast();

  const [year, setYear] = useState<number>(CURRENT_YEAR);
  const [monthMode, setMonthMode] = useState<MonthMode>("ytd");
  const [customMonths, setCustomMonths] = useState<Set<number>>(new Set());
  const [data, setData] = useState<ArboreProduseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [openBrands, setOpenBrands] = useState<Set<string>>(new Set());
  const [openCats, setOpenCats] = useState<Set<string>>(new Set());
  const [openSubs, setOpenSubs] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState<string>("");

  // Traduce state-ul modul/luni → argumentul pentru getArboreProduse.
  const monthsArg: number[] | "all" | undefined = useMemo(() => {
    if (monthMode === "ytd") return undefined;
    if (monthMode === "all") return "all";
    return Array.from(customMonths).sort((a, b) => a - b);
  }, [monthMode, customMonths]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getArboreProduse(apiScope, year, monthsArg)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((err) => {
        if (cancelled) return;
        toast.error(err instanceof ApiError ? err.message : "Eroare");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiScope, year, monthsArg, toast]);

  function toggleMonth(m: number) {
    // Primul clic din YTD/Toate doar TRECE în custom păstrând selecția
    // existentă (fără să toggleze luna clicată) — în custom-ul deja stabilit,
    // clicurile fac toggle normal (add/remove).
    if (monthMode !== "custom") {
      const seed: Set<number> = monthMode === "all"
        ? new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
        : new Set(data?.ytdMonths ?? []);
      seed.add(m);
      setCustomMonths(seed);
      setMonthMode("custom");
      return;
    }
    setCustomMonths((prev) => {
      const next = new Set(prev);
      next.has(m) ? next.delete(m) : next.add(m);
      return next;
    });
  }

  const grand = toNum(data?.grandSales);
  const allBrands = data?.brands ?? [];

  // Filtrare arbore pe query — păstrăm doar produsele cu match pe nume/cod;
  // categoriile/subgrupele/brandurile fără produse match sunt ascunse.
  const brands = useMemo<TreeBrand[]>(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allBrands;
    const matchProduct = (p: TreeProduct): boolean =>
      p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q);
    const out: TreeBrand[] = [];
    for (const b of allBrands) {
      const cats: TreeCategory[] = [];
      for (const c of b.categories) {
        const hasSubs = c.subgroups != null && c.subgroups.length > 0;
        if (hasSubs) {
          const subs: TreeSubgroup[] = [];
          for (const s of c.subgroups!) {
            const prods = s.products.filter(matchProduct);
            if (prods.length > 0) subs.push({ ...s, products: prods });
          }
          if (subs.length > 0) {
            cats.push({ ...c, subgroups: subs, products: c.products.filter(matchProduct) });
          }
        } else {
          const prods = c.products.filter(matchProduct);
          if (prods.length > 0) cats.push({ ...c, products: prods });
        }
      }
      if (cats.length > 0) out.push({ ...b, categories: cats });
    }
    return out;
  }, [allBrands, search]);

  // Când search e activ, considerăm toate nodurile expandate (vrem să vedem
  // rezultatele direct, fără să trebuiască să dăm click pe fiecare).
  const searchActive = search.trim().length > 0;

  const toggleBrand = (k: string) => {
    setOpenBrands((s) => {
      const n = new Set(s);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  };
  const toggleCat = (k: string) => {
    setOpenCats((s) => {
      const n = new Set(s);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  };
  const toggleSub = (k: string) => {
    setOpenSubs((s) => {
      const n = new Set(s);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  };

  const stackedSegments = useMemo(() => {
    if (grand <= 0) return [];
    return brands.map((b) => ({
      name: b.name,
      pct: (toNum(b.sales) / grand) * 100,
      color: brandColor(b),
    }));
  }, [brands, grand]);

  return (
    <div style={{
      padding: "4px 4px 20px", color: "var(--text)",
      zoom: 0.80 as unknown as number,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          🌲 Arbore Produse (Brand → Grupă → Produs)
        </h2>
        <label style={styles.label}>
          An
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={styles.select}
          >
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <input
          type="search"
          placeholder="Caută produs (cod sau denumire)…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-wide="true"
          style={styles.search}
        />
        <div style={{ marginLeft: "auto", fontSize: 12, color: "var(--fg-muted,#888)" }}>
          {year}: <b>{fmtRo(grand)}</b> · {year - 1}: {fmtRo(data?.grandSalesPrev)}
          {" "}<DiffPill pct={pctChange(data?.grandSales, data?.grandSalesPrev)} />
        </div>
      </div>

      {/* Month picker bar — grid 7 col × 2 rânduri (YTD + Tot anul + Nimic + 12 luni = 15 → 2 rânduri) */}
      <div style={styles.monthBar}>
        <div data-chipgrid="true" style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
          gap: 5, width: "100%",
        }}>
          {/* Rând 1: YTD, Tot anul, Nimic, Ian, Feb, Mar, Apr */}
          <button
            type="button"
            data-raw="true"
            onClick={() => { setMonthMode("ytd"); setCustomMonths(new Set()); }}
            style={chipStyle(monthMode === "ytd", "#16a34a")}
            title="Lunile cu date în anul curent"
          >
            YTD
          </button>
          <button
            type="button"
            data-raw="true"
            onClick={() => { setMonthMode("all"); setCustomMonths(new Set()); }}
            style={chipStyle(monthMode === "all", "#16a34a")}
          >
            Toate
          </button>
          <button
            type="button"
            data-raw="true"
            onClick={() => { setMonthMode("custom"); setCustomMonths(new Set()); }}
            style={chipStyle(monthMode === "custom" && customMonths.size === 0, "#dc2626")}
            title="Deselectează tot"
          >
            Nimic
          </button>
          {MONTH_ABBR.map((ab, i) => {
            const m = i + 1;
            const active = monthMode === "all"
              || (monthMode === "ytd" && (data?.ytdMonths ?? []).includes(m))
              || (monthMode === "custom" && customMonths.has(m));
            return (
              <button
                key={m}
                type="button"
                data-raw="true"
                onClick={() => toggleMonth(m)}
                style={chipStyle(active, "#16a34a")}
              >
                {ab}
              </button>
            );
          })}
        </div>
        {data?.selectedMonths && data.selectedMonths.length > 0 && (
          <span style={{ fontSize: 11, color: "var(--fg-muted,#888)" }}>
            activ: {data.selectedMonths.map((m) => MONTH_ABBR[m - 1]).join("·")}
          </span>
        )}
      </div>

      {/* Dashboard sus: card per brand + bară stacked proporțională */}
      {loading && !data ? (
        <TableSkeleton rows={3} cols={4} />
      ) : brands.length === 0 ? (
        <div style={styles.emptyCard}>Nu există date pentru scope-ul/anul selectat.</div>
      ) : (
        <>
          <div style={styles.dashGrid}>
            {brands.map((b) => {
              const pct = grand > 0 ? (toNum(b.sales) / grand) * 100 : 0;
              const delta = pctChange(b.sales, b.salesPrev);
              return (
                <div key={(b.brandId ?? b.name)} style={{
                  ...styles.dashCard,
                  borderLeft: `4px solid ${brandColor(b)}`,
                }}>
                  <div style={{ fontSize: 12, color: "var(--fg-muted,#888)" }}>
                    {b.isPrivateLabel ? "Marcă Privată" : "Brand"}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>{b.name}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                    {fmtRo(b.sales)}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--fg-muted,#888)",
                                display: "flex", alignItems: "center", gap: 6 }}>
                    vs {year - 1}: {fmtRo(b.salesPrev)} <DiffPill pct={delta} />
                  </div>
                  <div style={{ fontSize: 11, color: "var(--fg-muted,#888)" }}>
                    {pct.toFixed(1)}% · {b.categories.length} grupe
                  </div>
                  <div style={{
                    height: 6, background: "var(--bg-elevated,#eee)",
                    borderRadius: 3, overflow: "hidden", marginTop: 6,
                  }}>
                    <div style={{
                      width: `${pct}%`, height: "100%",
                      background: brandColor(b),
                    }} />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Bara stacked globală */}
          {stackedSegments.length > 0 && (
            <div style={{
              display: "flex", height: 22, borderRadius: 4, overflow: "hidden",
              border: "1px solid var(--border,#ddd)", marginBottom: 16,
              background: "var(--bg-elevated,#fafafa)",
            }}>
              {stackedSegments.map((s, i) => (
                <div
                  key={`${s.name}-${i}`}
                  title={`${s.name}: ${s.pct.toFixed(1)}%`}
                  style={{
                    width: `${s.pct}%`, background: s.color,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "#fff", fontSize: 11, fontWeight: 600,
                    overflow: "hidden", whiteSpace: "nowrap",
                  }}
                >
                  {s.pct >= 5 ? `${s.name} ${s.pct.toFixed(0)}%` : ""}
                </div>
              ))}
            </div>
          )}

          {searchActive && (
            <div style={{
              padding: "6px 10px", marginBottom: 8,
              background: "rgba(59,130,246,0.08)",
              border: "1px solid rgba(59,130,246,0.3)",
              borderRadius: 6, fontSize: 12,
            }}>
              Filtru activ: <b>{search}</b> ·{" "}
              {brands.reduce((sum, b) => sum + b.categories.reduce(
                (s, c) => s + (c.subgroups?.reduce((ss, sg) => ss + sg.products.length, 0)
                  ?? c.products.length), 0
              ), 0)} produse găsite în {brands.length} branduri
            </div>
          )}
          {/* Tree */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {brands.map((b) => {
              const bKey = b.brandId ?? b.name;
              const bOpen = searchActive || openBrands.has(bKey);
              return (
                <div key={bKey} style={{
                  ...styles.brandBlock,
                  borderLeft: `4px solid ${brandColor(b)}`,
                }}>
                  <div
                    onClick={() => toggleBrand(bKey)}
                    style={styles.brandHeader}
                    role="button"
                  >
                    <span style={{ width: 14, fontSize: 11 }}>{bOpen ? "▼" : "▶"}</span>
                    <b style={{ fontSize: 14 }}>{b.name}</b>
                    {b.isPrivateLabel && (
                      <span style={styles.plBadge}>Marcă Privată</span>
                    )}
                    <span style={{ flex: 1, fontSize: 13, color: "var(--muted, #666)" }}>
                      {fmtRo(b.sales)} · {b.categories.length} grupe ·{" "}
                      {b.categories.reduce((s, c) => s + c.products.length, 0)} produse
                    </span>
                    <DiffPill pct={pctChange(b.sales, b.salesPrev)} />
                  </div>
                  {bOpen && (
                    <div style={{ padding: "0 10px 10px 26px" }}>
                      {b.categories.map((c) => {
                        const catKey = bKey + "::" + (c.categoryId ?? c.label);
                        return (
                          <CategoryBlock
                            key={(c.categoryId ?? c.label) + bKey}
                            brandKey={bKey}
                            c={c}
                            open={searchActive || openCats.has(catKey)}
                            onToggle={() => toggleCat(catKey)}
                            openSubs={openSubs}
                            onToggleSub={toggleSub}
                            catKey={catKey}
                            searchActive={searchActive}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function ProductsTable({
  products, parentSales,
}: {
  products: TreeProduct[]; parentSales: string;
}) {
  const total = toNum(parentSales);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={th}>Produs</th>
            <th style={{ ...th, textAlign: "right" }}>Vânzări</th>
            <th style={{ ...th, textAlign: "right" }}>An preced.</th>
            <th style={{ ...th, textAlign: "right" }}>Δ%</th>
            <th style={{ ...th, textAlign: "right" }}>Cantitate</th>
            <th style={{ ...th, textAlign: "right" }}>Preț mediu</th>
            <th style={{ ...th, width: 100 }}>Pondere</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => {
            const pct = total > 0 ? (toNum(p.sales) / total) * 100 : 0;
            const delta = pctChange(p.sales, p.salesPrev);
            return (
              <tr key={p.productId}>
                <td style={td}>{p.name}</td>
                <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
                  {fmtRo(p.sales)}
                </td>
                <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums",
                             color: "var(--fg-muted,#888)" }}>
                  {fmtRo(p.salesPrev)}
                </td>
                <td style={{ ...td, textAlign: "right" }}>
                  <DiffPill pct={delta} />
                </td>
                <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {fmtRo(p.qty)}
                </td>
                <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {fmtPrice(p.avgPrice)}
                </td>
                <td style={td}>
                  <div style={{
                    height: 8, background: "var(--bg-elevated,#eee)",
                    borderRadius: 2, overflow: "hidden",
                  }}>
                    <div style={{
                      width: `${Math.min(100, pct)}%`, height: "100%",
                      background: "#3b82f6",
                    }} />
                  </div>
                  <div style={{ fontSize: 10, color: "var(--fg-muted,#888)" }}>
                    {pct.toFixed(1)}%
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SubgroupBlock({
  s, open, onToggle,
}: {
  s: TreeSubgroup; open: boolean; onToggle: () => void;
}) {
  return (
    <div style={styles.subBlock}>
      <div onClick={onToggle} style={styles.subHeader} role="button">
        <span style={{ width: 12, fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        <b style={{ fontSize: 12 }}>{s.label}</b>
        <span style={{ flex: 1, fontSize: 11, color: "var(--muted,#666)" }}>
          {fmtRo(s.sales)} · {s.products.length} produse · preț mediu{" "}
          <b style={{ color: "var(--text)" }}>{fmtPrice(s.avgPrice)}</b>
          {s.avgPricePrev && toNum(s.avgPricePrev) > 0 && (
            <span style={{ color: "var(--fg-muted,#888)" }}>
              {" "}(an prec.: {fmtPrice(s.avgPricePrev)})
            </span>
          )}
        </span>
        <DiffPill pct={pctChange(s.sales, s.salesPrev)} />
      </div>
      {open && <ProductsTable products={s.products} parentSales={s.sales} />}
    </div>
  );
}

function CategoryBlock({
  brandKey, c, open, onToggle, openSubs, onToggleSub, catKey, searchActive,
}: {
  brandKey: string; c: TreeCategory; open: boolean; onToggle: () => void;
  openSubs: Set<string>; onToggleSub: (k: string) => void; catKey: string;
  searchActive?: boolean;
}) {
  void brandKey;
  const hasSubgroups = c.subgroups != null && c.subgroups.length > 0;
  return (
    <div style={styles.catBlock}>
      <div onClick={onToggle} style={styles.catHeader} role="button">
        <span style={{ width: 12, fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        <b style={{ fontSize: 13 }}>{c.label}</b>
        <span style={{ color: "var(--fg-muted,#888)", fontSize: 11 }}>
          ({c.code})
        </span>
        <span style={{ flex: 1, fontSize: 12, color: "var(--muted, #666)" }}>
          {fmtRo(c.sales)}
          {hasSubgroups
            ? ` · ${c.subgroups!.length} subgrupe · ${c.products.length} produse`
            : ` · ${c.products.length} produse`}
        </span>
        <DiffPill pct={pctChange(c.sales, c.salesPrev)} />
      </div>
      {open && (
        hasSubgroups ? (
          <div style={{ padding: "4px 10px 8px 20px" }}>
            {c.subgroups!.map((s) => {
              const subKey = catKey + "::sub::" + s.key;
              return (
                <SubgroupBlock
                  key={subKey}
                  s={s}
                  open={searchActive || openSubs.has(subKey)}
                  onToggle={() => onToggleSub(subKey)}
                />
              );
            })}
          </div>
        ) : (
          <ProductsTable products={c.products} parentSales={c.sales} />
        )
      )}
    </div>
  );
}

function chipStyle(active: boolean, color: string): React.CSSProperties {
  return {
    padding: "4px 8px", fontSize: 11, fontWeight: 600,
    background: active ? color : "#f0f0f0",
    color: active ? "#fff" : "#444",
    border: `1px solid ${active ? color : "#ccc"}`,
    borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap",
    height: 26, minWidth: 0, textTransform: "lowercase" as const,
    fontFamily: "inherit",
  };
}

const styles: Record<string, React.CSSProperties> = {
  label: { display: "flex", flexDirection: "column", gap: 2, fontSize: 11, color: "var(--fg-muted,#666)" },
  select: { padding: 4, fontSize: 13, border: "1px solid var(--border,#ccc)", borderRadius: 4 },
  search: {
    padding: "6px 10px", fontSize: 13,
    border: "1px solid var(--border,#ccc)", borderRadius: 6,
    minWidth: 240, flex: "0 1 320px",
    background: "var(--card)", color: "var(--text)",
  },
  monthBar: {
    display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap",
    padding: "6px 8px",
    background: "var(--bg-elevated,#fafafa)",
    border: "1px solid var(--border,#eee)", borderRadius: 6,
    marginBottom: 10,
  },
  dashGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 10, marginBottom: 10,
  },
  dashCard: {
    background: "var(--bg-elevated,#fff)",
    border: "1px solid var(--border,#eee)",
    borderRadius: 6,
    padding: 10,
  },
  brandBlock: {
    background: "var(--bg-elevated,#fff)",
    border: "1px solid var(--border,#eee)",
    borderRadius: 6,
    overflow: "hidden",
  },
  brandHeader: {
    display: "flex", alignItems: "center", gap: 8, padding: "10px 12px",
    cursor: "pointer", userSelect: "none",
  },
  plBadge: {
    fontSize: 10, padding: "2px 6px", borderRadius: 3,
    background: "#a855f7", color: "#fff", fontWeight: 600,
  },
  catBlock: {
    background: "var(--bg,#fafafa)",
    border: "1px solid var(--border,#eee)",
    borderRadius: 4,
    marginBottom: 6,
  },
  catHeader: {
    display: "flex", alignItems: "center", gap: 6, padding: "6px 10px",
    cursor: "pointer", userSelect: "none",
  },
  subBlock: {
    background: "var(--bg-elevated,#fff)",
    border: "1px solid var(--border,#eee)",
    borderRadius: 3,
    marginBottom: 4,
  },
  subHeader: {
    display: "flex", alignItems: "center", gap: 6, padding: "5px 8px",
    cursor: "pointer", userSelect: "none",
  },
  table: { borderCollapse: "collapse", width: "100%" },
  emptyCard: {
    background: "var(--bg-elevated,#fafafa)",
    border: "1px solid var(--border,#eee)",
    borderRadius: 6, padding: 20,
    color: "var(--fg-muted,#888)", textAlign: "center",
  },
};
const th: React.CSSProperties = {
  textAlign: "left", padding: "6px 10px",
  borderBottom: "2px solid var(--border,#333)", fontSize: 12,
};
const td: React.CSSProperties = {
  padding: "4px 10px", borderBottom: "1px solid var(--border,#eee)", fontSize: 12,
};
