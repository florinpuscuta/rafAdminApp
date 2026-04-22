import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { getArboreProduse } from "./api";
import type {
  ArboreProduseResponse, TreeBrand, TreeCategory,
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
    setMonthMode("custom");
    setCustomMonths((s) => {
      const n = new Set(s);
      n.has(m) ? n.delete(m) : n.add(m);
      return n;
    });
  }

  const grand = toNum(data?.grandSales);
  const brands = data?.brands ?? [];

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
            data-compact="true"
            onClick={() => { setMonthMode("ytd"); setCustomMonths(new Set()); }}
            style={{ ...chipWhite(monthMode === "ytd", "#0ea5e9") }}
            title="Lunile cu date în anul curent"
          >
            YTD
          </button>
          <button
            type="button"
            data-compact="true"
            onClick={() => { setMonthMode("all"); setCustomMonths(new Set()); }}
            style={{ ...chipWhite(monthMode === "all", "#0ea5e9") }}
          >
            Toate
          </button>
          <button
            type="button"
            data-compact="true"
            onClick={() => { setMonthMode("custom"); setCustomMonths(new Set()); }}
            style={{ ...chipWhite(monthMode === "custom" && customMonths.size === 0, "#ef4444") }}
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
                data-compact="true"
                onClick={() => toggleMonth(m)}
                style={{ ...chipWhite(active, "#22c55e") }}
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

          {/* Tree */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {brands.map((b) => {
              const bKey = b.brandId ?? b.name;
              const bOpen = openBrands.has(bKey);
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
                      {b.categories.map((c) => (
                        <CategoryBlock
                          key={(c.categoryId ?? c.label) + bKey}
                          brandKey={bKey}
                          c={c}
                          open={openCats.has(bKey + "::" + (c.categoryId ?? c.label))}
                          onToggle={() =>
                            toggleCat(bKey + "::" + (c.categoryId ?? c.label))
                          }
                        />
                      ))}
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

function CategoryBlock({
  brandKey, c, open, onToggle,
}: {
  brandKey: string; c: TreeCategory; open: boolean; onToggle: () => void;
}) {
  void brandKey;
  return (
    <div style={styles.catBlock}>
      <div onClick={onToggle} style={styles.catHeader} role="button">
        <span style={{ width: 12, fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        <b style={{ fontSize: 13 }}>{c.label}</b>
        <span style={{ color: "var(--fg-muted,#888)", fontSize: 11 }}>
          ({c.code})
        </span>
        <span style={{ flex: 1, fontSize: 12, color: "var(--muted, #666)" }}>
          {fmtRo(c.sales)} · {c.products.length} produse
        </span>
        <DiffPill pct={pctChange(c.sales, c.salesPrev)} />
      </div>
      {open && (
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
              {c.products.map((p) => {
                const pct = toNum(c.sales) > 0
                  ? (toNum(p.sales) / toNum(c.sales)) * 100 : 0;
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
      )}
    </div>
  );
}

function chipWhite(active: boolean, color: string): React.CSSProperties {
  return {
    padding: "4px 6px", fontSize: 11, fontWeight: 600,
    background: active ? color : "#fff",
    color: active ? "#fff" : color,
    border: `1px solid ${active ? color : color + "55"}`,
    borderRadius: 8, cursor: "pointer", whiteSpace: "nowrap",
    minHeight: 30, minWidth: 0, textTransform: "lowercase" as const,
  };
}

const styles: Record<string, React.CSSProperties> = {
  label: { display: "flex", flexDirection: "column", gap: 2, fontSize: 11, color: "var(--fg-muted,#666)" },
  select: { padding: 4, fontSize: 13, border: "1px solid var(--border,#ccc)", borderRadius: 4 },
  monthBar: {
    display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap",
    padding: "6px 8px",
    background: "var(--bg-elevated,#fafafa)",
    border: "1px solid var(--border,#eee)", borderRadius: 6,
    marginBottom: 10,
  },
  modeBtn: {
    padding: "4px 10px", fontSize: 12, fontWeight: 600,
    border: "1px solid var(--border,#ccc)", borderRadius: 4,
    background: "var(--bg-elevated,#fff)", color: "var(--fg-muted,#555)",
    cursor: "pointer",
  },
  modeBtnActive: {
    background: "#0ea5e9", color: "#fff", borderColor: "#0ea5e9",
  },
  monthBtn: {
    width: 36, padding: "3px 0", fontSize: 11, fontWeight: 600,
    border: "1px solid var(--border,#ddd)", borderRadius: 3,
    background: "var(--bg-elevated,#fff)", color: "var(--fg-muted,#888)",
    cursor: "pointer", textTransform: "lowercase",
  },
  monthBtnActive: {
    background: "#22c55e", color: "#fff", borderColor: "#22c55e",
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
