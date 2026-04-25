import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getCostAnnual } from "./api";
import { fmtRo, toNum } from "./shared";
import type { AnnualCostResponse } from "./types";

const MONTHS_SHORT = [
  "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * Analiza costuri zona an — tabel pe an:
 *   rânduri = agenți (sortați după total descrescător),
 *   coloane = 12 luni + Total,
 *   rândul TOTAL de jos = suma pe fiecare lună + grand total.
 */
export default function CostAnualPage() {
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [data, setData] = useState<AnnualCostResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getCostAnnual(year));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => { void load(); }, [load]);

  const years = useMemo(() => {
    const curr = new Date().getFullYear();
    const out: number[] = [];
    for (let y = curr - 3; y <= curr + 1; y++) out.push(y);
    return out;
  }, []);

  return (
    <div className="agent-section" style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Analiza costuri zona an</h1>
          <p style={styles.lead}>
            Cost total per agent, defalcat pe cele 12 luni ale anului.
            Include salariu fix, bonus agent, merchandiser zonă, cheltuieli auto,
            alte cheltuieli și bonus raion.
          </p>
        </div>
        <div style={styles.picker}>
          <label style={styles.pickerLabel}>An</label>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={styles.select}
          >
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : !data || data.rows.length === 0 ? (
        <div style={styles.muted}>Nu sunt agenți activi.</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.thLeft}>Agent</th>
                {MONTHS_SHORT.map((m) => (
                  <th key={m} style={styles.th}>{m}</th>
                ))}
                <th style={styles.thTotal}>Total</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.agentId}>
                  <td style={styles.tdLeft}>{r.agentName}</td>
                  {r.monthly.map((v, i) => (
                    <td key={i} style={styles.td}>{fmtRo(toNum(v), 0)}</td>
                  ))}
                  <td style={styles.tdRowTotal}>{fmtRo(toNum(r.total), 0)}</td>
                </tr>
              ))}
              <tr>
                <td style={styles.tdTotalLabel}>TOTAL</td>
                {data.monthTotals.map((v, i) => (
                  <td key={i} style={styles.tdTotalNum}>{fmtRo(toNum(v), 0)}</td>
                ))}
                <td style={styles.tdGrand}>{fmtRo(toNum(data.grandTotal), 0)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "16px 8px", maxWidth: 1800 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 12, flexWrap: "wrap" },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: "0 0 4px" },
  lead: { color: "var(--muted)", fontSize: 12, margin: 0 },
  picker: {
    display: "inline-flex", alignItems: "center", gap: 8,
    padding: "6px 10px", background: "var(--bg-panel)",
    border: "1px solid var(--border)", borderRadius: 6,
  },
  pickerLabel: { fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" },
  select: {
    minWidth: 90, padding: "5px 8px", fontSize: 13,
    background: "var(--bg)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 4,
  },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "8px 12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "8px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "auto" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { padding: "10px 8px", textAlign: "right", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--muted)", whiteSpace: "nowrap" },
  thLeft: { padding: "10px 12px", textAlign: "left", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--muted)", whiteSpace: "nowrap" },
  thTotal: { padding: "10px 8px", textAlign: "right", fontSize: 11, fontWeight: 700, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--cyan)", whiteSpace: "nowrap" },
  td: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { padding: "6px 12px", textAlign: "left", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" },
  tdRowTotal: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", fontWeight: 700, color: "var(--cyan)" },
  tdTotalLabel: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)" },
  tdTotalNum: { padding: "10px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums" },
  tdGrand: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 800, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderLeft: "1px solid var(--border)" },
};
