import { useCallback, useEffect, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getCompensation, upsertCompensation } from "./api";
import { fmtRo, toNum } from "./shared";
import type { AgentCompRow } from "./types";

/**
 * Sal Fix — matricea constantelor de salariu per agent. Se introduc o
 * singură dată; valoarea persistă indefinit până la un nou upsert.
 * Coloana "Modificat" arată când a fost făcută ultima actualizare.
 */
export default function SalFixPage() {
  const [rows, setRows] = useState<AgentCompRow[]>([]);
  const [dirty, setDirty] = useState<Record<string, AgentCompRow>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCompensation();
      setRows(data.rows);
      setDirty({});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const patch = (
    agentId: string,
    field: keyof AgentCompRow,
    value: string | boolean | null,
  ) => {
    setDirty((prev) => {
      const base = prev[agentId] ?? rows.find((r) => r.agentId === agentId);
      if (!base) return prev;
      return { ...prev, [agentId]: { ...base, [field]: value } };
    });
  };

  const valueOf = (r: AgentCompRow, field: keyof AgentCompRow): string => {
    const d = dirty[r.agentId];
    const src = d ?? r;
    const v = src[field];
    return v == null ? "" : String(v);
  };

  const save = async (agentId: string) => {
    const row = dirty[agentId];
    if (!row) return;
    setSavingId(agentId);
    setError(null);
    try {
      const updated = await upsertCompensation({
        agentId: row.agentId,
        salariuFix: row.salariuFix || "0",
        bonusVanzariEligibil: row.bonusVanzariEligibil,
        note: row.note,
      });
      setRows((prev) => prev.map((r) => (r.agentId === agentId ? updated : r)));
      setDirty((prev) => {
        const next = { ...prev };
        delete next[agentId];
        return next;
      });
      setFlash(`Salvat: ${updated.agentName}`);
      setTimeout(() => setFlash(null), 2000);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la salvare");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Sal Fix</h1>
          <p style={styles.lead}>
            Salariul fix per agent — se introduce o dată și rămâne constant
            până la o nouă actualizare. Coloana „Modificat" arată data ultimei
            schimbări.
          </p>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {flash && <div style={styles.flash}>{flash}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : rows.length === 0 ? (
        <div style={styles.muted}>Nu există agenți activi.</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.thLeft}>Agent</th>
                <th style={styles.th}>Sal. fix (RON)</th>
                <th style={styles.thCenter}>Eligibil bonus</th>
                <th style={styles.thLeft}>Note</th>
                <th style={styles.thLeft}>Modificat</th>
                <th style={styles.th}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const isDirty = Boolean(dirty[r.agentId]);
                const isSaving = savingId === r.agentId;
                const eligibil = (dirty[r.agentId] ?? r).bonusVanzariEligibil;
                return (
                  <tr key={r.agentId} style={isDirty ? styles.rowDirty : undefined}>
                    <td style={styles.tdLeft}>{r.agentName}</td>
                    <td style={styles.td}>
                      <input
                        data-raw="true"
                        type="number" step="0.01"
                        style={styles.inpNum}
                        value={valueOf(r, "salariuFix")}
                        onChange={(e) => patch(r.agentId, "salariuFix", e.target.value)}
                      />
                    </td>
                    <td style={styles.tdCenter}>
                      <input
                        type="checkbox"
                        checked={eligibil}
                        onChange={(e) => patch(r.agentId, "bonusVanzariEligibil", e.target.checked)}
                        style={styles.chk}
                        title={eligibil ? "Primește bonus de vânzări" : "NU primește bonus de vânzări"}
                      />
                    </td>
                    <td style={styles.tdLeft}>
                      <input
                        data-raw="true"
                        type="text"
                        style={styles.inpText}
                        value={valueOf(r, "note")}
                        onChange={(e) => patch(r.agentId, "note", e.target.value)}
                        placeholder="—"
                      />
                    </td>
                    <td style={styles.tdLeft}>
                      {r.updatedAt ? (
                        <span style={styles.updatedBadge}>
                          {fmtDateTime(r.updatedAt)}
                        </span>
                      ) : (
                        <span style={styles.muted}>niciodată</span>
                      )}
                    </td>
                    <td style={styles.td}>
                      <button
                        data-wide="true"
                        onClick={() => save(r.agentId)}
                        disabled={!isDirty || isSaving}
                        style={{
                          ...styles.saveBtn,
                          opacity: isDirty && !isSaving ? 1 : 0.5,
                          cursor: isDirty && !isSaving ? "pointer" : "default",
                        }}
                      >
                        {isSaving ? "…" : "Salvează"}
                      </button>
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td style={styles.tdTotal}>TOTAL</td>
                <td style={styles.tdTotalNum}>
                  {fmtRo(rows.reduce((s, r) => s + toNum(valueOf(r, "salariuFix")), 0), 0)}
                </td>
                <td style={styles.tdTotal} colSpan={4}></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "12px 8px", width: "100%" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 10, flexWrap: "wrap" },
  title: { fontSize: 18, fontWeight: 700, color: "var(--cyan)", margin: "0 0 2px" },
  lead: { color: "var(--muted)", fontSize: 11, margin: 0, maxWidth: 640, lineHeight: 1.4 },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "6px 10px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  flash: { padding: "6px 10px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.4)", color: "#86efac", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: { padding: "8px 6px", textAlign: "right", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thLeft: { padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thCenter: { padding: "8px 10px", textAlign: "center", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  td: { padding: "4px 6px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { padding: "4px 10px", textAlign: "left", borderBottom: "1px solid var(--border)" },
  tdCenter: { padding: "4px 10px", textAlign: "center", borderBottom: "1px solid var(--border)" },
  chk: { width: 16, height: 16, cursor: "pointer", accentColor: "var(--cyan)" },
  rowDirty: { background: "rgba(234,179,8,0.06)" },
  inpNum: { width: 120, padding: "3px 4px", textAlign: "right", fontSize: 12, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, fontVariantNumeric: "tabular-nums", boxSizing: "border-box" },
  inpText: { width: "100%", minWidth: 0, padding: "3px 4px", fontSize: 12, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, boxSizing: "border-box" },
  saveBtn: { padding: "4px 10px", fontSize: 11, fontWeight: 600, background: "var(--cyan)", color: "#000", border: "none", borderRadius: 4, minWidth: 72 },
  updatedBadge: {
    display: "inline-block",
    padding: "2px 8px",
    fontSize: 11,
    background: "rgba(34,197,94,0.12)",
    color: "#86efac",
    border: "1px solid rgba(34,197,94,0.35)",
    borderRadius: 4,
    fontVariantNumeric: "tabular-nums",
  },
  tdTotal: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "2px solid var(--border)" },
  tdTotalNum: { padding: "10px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
};
