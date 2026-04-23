import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getAgentAnnual, getCompensation } from "./api";
import { MONTHS_RO, fmtRo, toNum } from "./shared";
import type { AgentAnnualResponse, AgentCompRow } from "./types";

/**
 * Analiza anuală pe agent — selectezi un agent + un an și vezi tabelul:
 *   rânduri = cele 12 luni,
 *   coloane = categorii (sal. fix, bonus agent, merchandiser zonă, cheltuieli
 *             auto, alte cheltuieli, bonus raion) + Total,
 *   rândul TOTAL de jos = suma pe fiecare categorie + grand total.
 */
export default function AgentAnualPage() {
  const [agents, setAgents] = useState<AgentCompRow[]>([]);
  const [agentId, setAgentId] = useState<string>("");
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [data, setData] = useState<AgentAnnualResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const list = await getCompensation();
        const rows = [...list.rows].sort((a, b) => a.agentName.localeCompare(b.agentName));
        setAgents(rows);
        if (rows.length > 0 && !agentId) setAgentId(rows[0].agentId);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Eroare la încărcare agenți");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(async () => {
    if (!agentId) { setData(null); return; }
    setLoading(true);
    setError(null);
    try {
      setData(await getAgentAnnual(agentId, year));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [agentId, year]);

  useEffect(() => { void load(); }, [load]);

  const years = useMemo(() => {
    const curr = new Date().getFullYear();
    const out: number[] = [];
    for (let y = curr - 3; y <= curr + 1; y++) out.push(y);
    return out;
  }, []);

  const totals = data?.columnTotals;

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Analiza anuală pe agent</h1>
          <p style={styles.lead}>
            Cheltuielile lunare defalcate pe categorii, pentru un agent, pe un an întreg.
          </p>
        </div>
        <div style={styles.picker}>
          <label style={styles.pickerLabel}>Agent</label>
          <select
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            style={styles.selectAgent}
            size={1}
          >
            {agents.map((a) => (
              <option key={a.agentId} value={a.agentId}>{a.agentName}</option>
            ))}
          </select>
          <label style={styles.pickerLabel}>An</label>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={styles.selectYear}
          >
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : !data ? (
        <div style={styles.muted}>Selectează un agent.</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.thLeft}>Luna</th>
                <th style={styles.th}>Sal. fix</th>
                <th style={styles.th}>Bonus agent</th>
                <th style={styles.th}>Merchandiser zonă</th>
                <th style={styles.th}>Cheltuieli auto</th>
                <th style={styles.th}>Alte cheltuieli</th>
                <th style={styles.th}>Bonus raion</th>
                <th style={styles.thTotal}>Total</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.month}>
                  <td style={styles.tdLeft}>{MONTHS_RO[r.month - 1]}</td>
                  <td style={styles.td}>{fmtRo(toNum(r.salariuFix), 0)}</td>
                  <td style={styles.td}>{fmtRo(toNum(r.bonusAgent), 0)}</td>
                  <td style={styles.td}>{fmtRo(toNum(r.merchandiserZona), 0)}</td>
                  <td style={styles.td}>{fmtRo(toNum(r.cheltuieliAuto), 0)}</td>
                  <td style={styles.td}>{fmtRo(toNum(r.alteCheltuieli), 0)}</td>
                  <td style={styles.td}>{fmtRo(toNum(r.bonusRaion), 0)}</td>
                  <td style={styles.tdRowTotal}>{fmtRo(toNum(r.total), 0)}</td>
                </tr>
              ))}
              {totals && (
                <tr>
                  <td style={styles.tdTotalLabel}>TOTAL</td>
                  <td style={styles.tdTotalNum}>{fmtRo(toNum(totals.salariuFix), 0)}</td>
                  <td style={styles.tdTotalNum}>{fmtRo(toNum(totals.bonusAgent), 0)}</td>
                  <td style={styles.tdTotalNum}>{fmtRo(toNum(totals.merchandiserZona), 0)}</td>
                  <td style={styles.tdTotalNum}>{fmtRo(toNum(totals.cheltuieliAuto), 0)}</td>
                  <td style={styles.tdTotalNum}>{fmtRo(toNum(totals.alteCheltuieli), 0)}</td>
                  <td style={styles.tdTotalNum}>{fmtRo(toNum(totals.bonusRaion), 0)}</td>
                  <td style={styles.tdGrand}>{fmtRo(toNum(totals.total), 0)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "16px 8px", maxWidth: 1400 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 12, flexWrap: "wrap" },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: "0 0 4px" },
  lead: { color: "var(--muted)", fontSize: 12, margin: 0 },
  picker: {
    display: "inline-flex", alignItems: "center", gap: 8,
    padding: "6px 10px", background: "var(--bg-panel)",
    border: "1px solid var(--border)", borderRadius: 6,
  },
  pickerLabel: { fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" },
  selectAgent: {
    minWidth: 220, padding: "5px 8px", fontSize: 13,
    background: "var(--bg)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 4,
  },
  selectYear: {
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
