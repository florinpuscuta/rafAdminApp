import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../../shared/api";
import { CollapsibleBlock } from "../../shared/ui/CollapsibleBlock";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { groupByEpsSubgroup, isEpsCategory } from "../../shared/utils/epsSubgroup";
import { downloadTableAsCsv } from "../../shared/utils/exportCsv";
import { sikaTm } from "../../shared/utils/sikaTm";
import { getPropuneriListare } from "./api";
import type { PropuneriFilters, PropuneriResponse, PropunereRow } from "./types";

const MONTHS = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

const KA_LABELS: Record<string, string> = {
  DEDEMAN: "Dedeman", LEROY: "Leroy Merlin", HORNBACH: "Hornbach",
  ALTEX: "Altex",
};
const KA_COLORS: Record<string, string> = {
  DEDEMAN: "#22c55e", LEROY: "#3b82f6", HORNBACH: "#f59e0b",
  ALTEX: "#ef4444",
};

function fmtFull(v: string | number | null | undefined): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

function fmtPrice(v: string | null | undefined): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PropuneriKaListarePage() {
  const { scope } = useCompanyScope();
  const company = scope === "sika" ? "sika" : scope === "sikadp" ? "sikadp" : "adeplast";
  const toast = useToast();
  const [data, setData] = useState<PropuneriResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<PropuneriFilters>({ year: CURRENT_YEAR, company });
  const [activeKa, setActiveKa] = useState<string>("");
  const tableRef = useRef<HTMLTableElement>(null);

  const load = useCallback(async (f: PropuneriFilters) => {
    setLoading(true);
    try {
      const resp = await getPropuneriListare(f);
      setData(resp);
      // Auto-select primul KA când nu e nimic ales
      if (!activeKa && resp.kaClients.length > 0) {
        setActiveKa(resp.kaClients[0]);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setFilters((prev) => ({ ...prev, company }));
  }, [company]);

  useEffect(() => { load(filters); }, [filters, load]);

  const kaClients = data?.kaClients ?? [];
  const currentList = data?.suggestions[activeKa] ?? [];

  const otherKas = useMemo(() => kaClients.filter((k) => k !== activeKa), [kaClients, activeKa]);

  const isSika = scope === "sika";

  // Grupare pe categorie pentru KA-ul activ.
  // La Sika folosim TM (Target Market) în loc de category_code.
  const byCategory = useMemo(() => {
    const out: Record<string, PropunereRow[]> = {};
    for (const row of currentList) {
      const key = isSika ? sikaTm(row.description) : row.category;
      if (!out[key]) out[key] = [];
      out[key].push(row);
    }
    // Sortare categorii pe total vânzări desc
    const entries = Object.entries(out).sort(([, a], [, b]) => {
      const sa = a.reduce((s, p) => s + Number(p.totalSales || 0), 0);
      const sb = b.reduce((s, p) => s + Number(p.totalSales || 0), 0);
      return sb - sa;
    });
    return entries;
  }, [currentList, isSika]);

  function update(patch: Partial<PropuneriFilters>) {
    const next = { ...filters, ...patch };
    (Object.keys(next) as (keyof PropuneriFilters)[]).forEach((k) => {
      const v = next[k];
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
        delete next[k];
      }
    });
    setFilters(next);
  }

  return (
    <div style={{
      padding: "4px 4px 20px", color: "var(--text)",
      zoom: 0.80 as unknown as number,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          📋 Propuneri Listare KA
        </h2>
        <button
          type="button"
          data-compact="true"
          onClick={() => downloadTableAsCsv(tableRef.current, "propuneri-listare-ka.csv")}
          style={{
            marginLeft: "auto", padding: "6px 10px", fontSize: 12, fontWeight: 600,
            background: "#16a34a", color: "#fff", border: "none",
            borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap", minHeight: 34,
          }}
          title="Descarcă tabelul ca Excel"
        >
          ⬇ Excel
        </button>
      </div>
      <p style={{ color: "var(--fg-muted, #666)", fontSize: 14, marginTop: 0 }}>
        Produse vândute la alte rețele KA dar nelistate la retailerul selectat.
        Prețul minim este cel mai mic preț de facturare găsit la celelalte rețele.
      </p>

      <div style={styles.filterBar}>
        <label style={styles.label}>
          An
          <select
            value={filters.year ?? ""}
            onChange={(e) => update({ year: e.target.value ? Number(e.target.value) : undefined })}
            style={styles.select}
          >
            <option value="">toate</option>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <label style={styles.label}>
          Lună
          <select
            value={(filters.months && filters.months[0]) ?? ""}
            onChange={(e) => update({
              months: e.target.value ? [Number(e.target.value)] : undefined,
            })}
            style={styles.select}
            disabled={!filters.year}
          >
            <option value="">toate</option>
            {MONTHS.map((name, i) => (
              <option key={i + 1} value={i + 1}>{name}</option>
            ))}
          </select>
        </label>
      </div>

      {kaClients.length > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
          {kaClients.map((ka) => {
            const cnt = data?.suggestions[ka]?.length ?? 0;
            const active = activeKa === ka;
            return (
              <button
                key={ka}
                onClick={() => setActiveKa(ka)}
                style={{
                  padding: "8px 18px",
                  borderRadius: 6,
                  border: `2px solid ${KA_COLORS[ka] ?? "#666"}`,
                  background: active ? (KA_COLORS[ka] ?? "#666") : "transparent",
                  color: active ? "#fff" : (KA_COLORS[ka] ?? "#333"),
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                {KA_LABELS[ka] ?? ka} <span style={{ fontSize: 11, opacity: 0.9 }}>({cnt})</span>
              </button>
            );
          })}
        </div>
      )}

      {loading && !data ? (
        <TableSkeleton rows={8} cols={6} />
      ) : activeKa && currentList.length === 0 ? (
        <div style={styles.emptyCard}>
          Toate produsele sunt deja listate la {KA_LABELS[activeKa] ?? activeKa}.
        </div>
      ) : (
        byCategory.map(([cat, items], catIdx) => {
          const catSales = items.reduce((s, p) => s + Number(p.totalSales || 0), 0);
          const isEps = !isSika && isEpsCategory(cat);
          const epsGroups = isEps
            ? groupByEpsSubgroup(items, (p) => p.description, (p) => p.totalSales)
            : null;

          const headerRow = (
            <tr>
              <th style={th}>Produs</th>
              <th style={{ ...th, textAlign: "right" }}>Vânzări alte KA</th>
              <th style={{ ...th, textAlign: "right" }}>Cantitate</th>
              <th style={{ ...th, textAlign: "right" }}>Preț min</th>
              <th style={{ ...th, textAlign: "center" }}>Sursă preț</th>
              <th style={{ ...th, textAlign: "right" }}>Nr. rețele</th>
              {otherKas.map((ok) => (
                <th key={ok} style={{ ...th, textAlign: "right", color: KA_COLORS[ok] }}>
                  {KA_LABELS[ok] ?? ok}
                </th>
              ))}
            </tr>
          );

          const renderRow = (p: PropunereRow, i: number) => (
            <tr key={`${p.description}-${i}`}>
              <td style={td}>{p.description}</td>
              <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {fmtFull(p.totalSales)}
              </td>
              <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                {fmtFull(p.totalQty)}
              </td>
              <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 700 }}>
                {fmtPrice(p.minPrice)}
              </td>
              <td style={{ ...td, textAlign: "center", color: KA_COLORS[p.minPriceKa] ?? "inherit", fontWeight: 600 }}>
                {KA_LABELS[p.minPriceKa] ?? p.minPriceKa}
              </td>
              <td style={{ ...td, textAlign: "right" }}>{p.numKas}</td>
              {otherKas.map((ok) => (
                <td key={ok} style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums", color: KA_COLORS[ok] }}>
                  {p.prices[ok] ? fmtPrice(p.prices[ok]) : "—"}
                </td>
              ))}
            </tr>
          );

          return (
            <div key={cat} style={styles.catBlock}>
              <CollapsibleBlock
                title={cat}
                subtitle={`${items.length} produse nelistate · vânzări alte rețele: ${fmtFull(catSales)}`}
              >
                {isEps && epsGroups ? (
                  epsGroups.map((g, gi) => (
                    <div key={g.key} style={styles.subBlock}>
                      <CollapsibleBlock
                        title={g.label}
                        subtitle={`${g.products.length} produse · ${fmtFull(g.totalSales)}`}
                        level={1}
                      >
                        <div style={{ overflowX: "auto" }}>
                          <table ref={catIdx === 0 && gi === 0 ? tableRef : undefined} style={styles.table}>
                            <thead>{headerRow}</thead>
                            <tbody>{g.products.map(renderRow)}</tbody>
                          </table>
                        </div>
                      </CollapsibleBlock>
                    </div>
                  ))
                ) : (
                  <div style={{ overflowX: "auto" }}>
                    <table ref={catIdx === 0 ? tableRef : undefined} style={styles.table}>
                      <thead>{headerRow}</thead>
                      <tbody>{items.map(renderRow)}</tbody>
                    </table>
                  </div>
                )}
              </CollapsibleBlock>
            </div>
          );
        })
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  filterBar: {
    display: "flex", gap: 12, padding: "10px 12px",
    background: "var(--bg-elevated, #fafafa)",
    border: "1px solid var(--border, #eee)", borderRadius: 6,
    marginBottom: 16, flexWrap: "wrap", alignItems: "flex-end",
  },
  label: { display: "flex", flexDirection: "column", gap: 3, fontSize: 12, color: "var(--fg-muted, #666)" },
  select: { padding: 6, fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4 },
  catBlock: {
    background: "var(--bg-elevated, #fff)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    padding: 12,
    marginBottom: 12,
  },
  subBlock: {
    background: "var(--bg, #fafafa)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 4,
    padding: 8,
    marginBottom: 8,
  },
  subHeader: {
    display: "flex",
    alignItems: "center",
    marginBottom: 6,
  },
  emptyCard: {
    background: "var(--bg-elevated, #fafafa)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    padding: 20,
    color: "var(--fg-muted, #888)",
    textAlign: "center",
  },
  table: { borderCollapse: "collapse", width: "100%" },
};
const th: React.CSSProperties = {
  textAlign: "left", padding: "8px 12px",
  borderBottom: "2px solid var(--border, #333)", fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px", borderBottom: "1px solid var(--border, #eee)", fontSize: 13,
};
