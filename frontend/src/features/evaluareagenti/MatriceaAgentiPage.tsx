import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getMatrix } from "./api";
import { MonthYearPicker, fmtRo, toNum, useEvaluareYearMonth } from "./shared";
import type { MatrixResponse, MatrixRow } from "./types";

type SortKey = keyof MatrixRow;

/**
 * Matricea Agenți — agregă pe o lună: vânzări, salariu fix + bonus (din
 * /bonusari), telefon, diurnă, carburant (km × consum × preț), bonusări
 * oameni raion, cost total, cost per 100.000 RON vânzări.
 */
export default function MatriceaAgentiPage() {
  const { year, month, setYearMonth } = useEvaluareYearMonth();
  const [data, setData] = useState<MatrixResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("vanzari");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getMatrix(year, month));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => { void load(); }, [load]);

  const sortedRows = useMemo<MatrixRow[]>(() => {
    if (!data) return [];
    const rows = [...data.rows];
    rows.sort((a, b) => {
      const av = a[sortBy];
      const bv = b[sortBy];
      const an = typeof av === "number" ? av : toNum(av as string | null);
      const bn = typeof bv === "number" ? bv : toNum(bv as string | null);
      if (!Number.isFinite(an) && !Number.isFinite(bn)) {
        return String(av ?? "").localeCompare(String(bv ?? ""));
      }
      const cmp = an - bn;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [data, sortBy, sortDir]);

  const toggleSort = (k: SortKey) => {
    if (sortBy === k) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(k); setSortDir("desc"); }
  };

  const Th = ({ k, label, align }: { k: SortKey; label: string; align?: "left" | "right" }) => {
    const active = sortBy === k;
    return (
      <th
        onClick={() => toggleSort(k)}
        style={{
          ...(align === "left" ? styles.thLeft : styles.th),
          cursor: "pointer",
          color: active ? "var(--cyan)" : "var(--muted)",
        }}
        title="Sortează"
      >
        {label}{active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </th>
    );
  };

  const grandVanzari = toNum(data?.grandVanzari);
  const grandCost = toNum(data?.grandCost);
  const grandPer100k = grandVanzari > 0 ? grandCost / (grandVanzari / 100_000) : 0;

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Matricea Agenți</h1>
          <p style={styles.lead}>
            O linie per agent — vânzări, salariu (fix + bonus), costuri
            operaționale, cost/100.000 RON vânzări.
          </p>
        </div>
        <MonthYearPicker
          year={year} month={month}
          onChange={(y, m) => setYearMonth(y, m)}
        />
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : !data || sortedRows.length === 0 ? (
        <div style={styles.muted}>Nu sunt date pentru această lună.</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <Th k="agentName" label="Agent" align="left" />
                <Th k="vanzari" label="Vânzări" />
                <Th k="salariuFix" label="Sal. fix" />
                <Th k="bonusAgent" label="Bonus agent" />
                <Th k="salariuTotal" label="Sal. total" />
                <Th k="costCombustibil" label="Combustibil" />
                <Th k="costRevizii" label="Revizii" />
                <Th k="alteCosturi" label="Alte" />
                <Th k="bonusRaion" label="Bonus raion" />
                <Th k="totalCost" label="Cost total" />
                <Th k="costPer100k" label="Cost / 100k" />
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((r) => {
                const cp = r.costPer100k == null ? null : toNum(r.costPer100k);
                return (
                  <tr key={r.agentId}>
                    <td style={styles.tdLeft}>{r.agentName}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.vanzari), 0)}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.salariuFix), 0)}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.bonusAgent), 0)}</td>
                    <td style={{ ...styles.td, fontWeight: 600 }}>{fmtRo(toNum(r.salariuTotal), 0)}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.costCombustibil), 0)}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.costRevizii), 0)}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.alteCosturi), 0)}</td>
                    <td style={styles.td}>{fmtRo(toNum(r.bonusRaion), 0)}</td>
                    <td style={{ ...styles.td, fontWeight: 700 }}>{fmtRo(toNum(r.totalCost), 0)}</td>
                    <td style={{ ...styles.td, fontWeight: 700, color: cp == null ? "var(--muted)" : colorForCost(cp) }}>
                      {cp == null ? "—" : fmtRo(cp, 0)}
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td style={styles.tdTotal}>TOTAL</td>
                <td style={styles.tdTotalNum}>{fmtRo(grandVanzari, 0)}</td>
                <td style={styles.tdTotal} colSpan={7}></td>
                <td style={styles.tdTotalNum}>{fmtRo(grandCost, 0)}</td>
                <td style={styles.tdTotalNum}>
                  {grandVanzari > 0 ? fmtRo(grandPer100k, 0) : "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function colorForCost(costPer100k: number): string {
  // <5000 RON cost/100k vz = verde; >12000 = roșu; între = galben
  if (costPer100k < 5000) return "#4ade80";
  if (costPer100k > 12000) return "#ef4444";
  return "#fbbf24";
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "16px 8px", maxWidth: 1800 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 12, flexWrap: "wrap" },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: "0 0 4px" },
  lead: { color: "var(--muted)", fontSize: 12, margin: 0 },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "8px 12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "8px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "auto" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { padding: "10px 8px", textAlign: "right", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thLeft: { padding: "10px 12px", textAlign: "left", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  td: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdMuted: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", color: "var(--muted)" },
  tdLeft: { padding: "6px 12px", textAlign: "left", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" },
  tdTotal: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)" },
  tdTotalNum: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums" },
};
