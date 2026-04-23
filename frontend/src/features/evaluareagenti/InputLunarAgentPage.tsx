import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getMonthInputs, upsertMonthInput } from "./api";
import { MonthYearPicker, fmtRo, toNum, useEvaluareYearMonth } from "./shared";
import type { MonthInputRow } from "./types";

/**
 * Input Lunar Agent — matricea lunară a costurilor per agent.
 * Coloane readonly (auto): salariu fix (pachet), bonus agent (/bonusari),
 * bonus zonă (/raion-bonus). Coloane editabile în RON: combustibil, revizii,
 * alte costuri. TOTAL = suma tuturor.
 */
export default function InputLunarAgentPage() {
  const { year, month, setYearMonth } = useEvaluareYearMonth();
  const [rows, setRows] = useState<MonthInputRow[]>([]);
  const [dirty, setDirty] = useState<Record<string, MonthInputRow>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMonthInputs(year, month);
      setRows(data.rows);
      setDirty({});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => { void load(); }, [load]);

  const patch = (agentId: string, field: keyof MonthInputRow, value: string | null) => {
    setDirty((prev) => {
      const base = prev[agentId] ?? rows.find((r) => r.agentId === agentId);
      if (!base) return prev;
      return { ...prev, [agentId]: { ...base, [field]: value } };
    });
  };

  const valueOf = (r: MonthInputRow, field: keyof MonthInputRow): string => {
    const d = dirty[r.agentId];
    const src = d ?? r;
    const v = src[field];
    return v == null ? "" : String(v);
  };

  const previewTotal = (r: MonthInputRow): number => {
    const src = dirty[r.agentId] ?? r;
    return (
      toNum(src.salariuFix)
      + toNum(src.bonusAgent)
      + toNum(src.costCombustibil)
      + toNum(src.costRevizii)
      + toNum(src.alteCosturi)
      + toNum(src.bonusRaion)
    );
  };

  const save = async (agentId: string) => {
    const row = dirty[agentId];
    if (!row) return;
    setSavingId(agentId);
    setError(null);
    try {
      const updated = await upsertMonthInput({
        agentId: row.agentId,
        year: row.year,
        month: row.month,
        costCombustibil: row.costCombustibil || "0",
        costRevizii: row.costRevizii || "0",
        alteCosturi: row.alteCosturi || "0",
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

  const sortedRows = useMemo<MonthInputRow[]>(
    () => [...rows].sort((a, b) => toNum(b.vanzari) - toNum(a.vanzari)),
    [rows],
  );

  const totals = rows.reduce((acc, r) => {
    const src = dirty[r.agentId] ?? r;
    acc.vanzari += toNum(src.vanzari);
    acc.salariuFix += toNum(src.salariuFix);
    acc.bonusAgent += toNum(src.bonusAgent);
    acc.costCombustibil += toNum(src.costCombustibil);
    acc.costRevizii += toNum(src.costRevizii);
    acc.alteCosturi += toNum(src.alteCosturi);
    acc.bonusRaion += toNum(src.bonusRaion);
    acc.total += previewTotal(r);
    return acc;
  }, {
    vanzari: 0, salariuFix: 0, bonusAgent: 0, costCombustibil: 0,
    costRevizii: 0, alteCosturi: 0, bonusRaion: 0, total: 0,
  });

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Input Lunar Agent</h1>
          <p style={styles.lead}>
            Matricea lunară a costurilor per agent. Salariu fix vine din Pachet
            Salarial, bonusul din Bonusări, bonus zonă din Bonusări Raion.
            Combustibil, revizii și alte costuri se introduc manual în RON.
          </p>
        </div>
        <MonthYearPicker
          year={year} month={month}
          onChange={(y, m) => setYearMonth(y, m)}
        />
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
                <th style={styles.th}>Vânzări</th>
                <th style={styles.th}>Sal. fix</th>
                <th style={styles.th}>Bonus</th>
                <th style={styles.th}>Combustibil</th>
                <th style={styles.th}>Revizii</th>
                <th style={styles.th}>Alte costuri</th>
                <th style={styles.th}>Bonus zonă</th>
                <th style={styles.th}>TOTAL</th>
                <th style={styles.thLeft}>Note</th>
                <th style={styles.th}></th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((r) => {
                const isDirty = Boolean(dirty[r.agentId]);
                const isSaving = savingId === r.agentId;
                const total = previewTotal(r);
                return (
                  <tr key={r.agentId} style={isDirty ? styles.rowDirty : undefined}>
                    <td style={styles.tdLeft}>{r.agentName}</td>
                    <td style={{ ...styles.td, fontWeight: 600 }}>{fmtRo(toNum(r.vanzari), 0)}</td>
                    <td style={styles.tdRoRight}>{fmtRo(toNum(r.salariuFix), 0)}</td>
                    <td style={styles.tdRoRight}>{fmtRo(toNum(r.bonusAgent), 0)}</td>
                    <td style={styles.td}>
                      <input
                        data-raw="true"
                        type="number" step="0.01"
                        style={styles.inpNum}
                        value={valueOf(r, "costCombustibil")}
                        onChange={(e) => patch(r.agentId, "costCombustibil", e.target.value)}
                      />
                    </td>
                    <td style={styles.td}>
                      <input
                        data-raw="true"
                        type="number" step="0.01"
                        style={styles.inpNum}
                        value={valueOf(r, "costRevizii")}
                        onChange={(e) => patch(r.agentId, "costRevizii", e.target.value)}
                      />
                    </td>
                    <td style={styles.td}>
                      <input
                        data-raw="true"
                        type="number" step="0.01"
                        style={styles.inpNum}
                        value={valueOf(r, "alteCosturi")}
                        onChange={(e) => patch(r.agentId, "alteCosturi", e.target.value)}
                      />
                    </td>
                    <td style={styles.tdRoRight}>{fmtRo(toNum(r.bonusRaion), 0)}</td>
                    <td style={{ ...styles.td, fontWeight: 700, color: "var(--cyan)" }}>
                      {fmtRo(total, 0)}
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
                <td style={styles.tdTotalNum}>{fmtRo(totals.vanzari, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.salariuFix, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.bonusAgent, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.costCombustibil, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.costRevizii, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.alteCosturi, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.bonusRaion, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.total, 0)}</td>
                <td style={styles.tdTotal} colSpan={2}></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "16px 8px", maxWidth: 1700 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 12, flexWrap: "wrap" },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: "0 0 4px" },
  lead: { color: "var(--muted)", fontSize: 12, margin: 0, maxWidth: 700, lineHeight: 1.5 },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "8px 12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "8px 0" },
  flash: { padding: "8px 12px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.4)", color: "#86efac", borderRadius: 6, fontSize: 12, margin: "8px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "auto" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { padding: "10px 8px", textAlign: "right", fontSize: 11, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thLeft: { padding: "10px 12px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  td: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdRoRight: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", color: "var(--muted)" },
  tdLeft: { padding: "6px 12px", textAlign: "left", borderBottom: "1px solid var(--border)" },
  rowDirty: { background: "rgba(234,179,8,0.06)" },
  inpNum: { width: 100, padding: "4px 6px", textAlign: "right", fontSize: 13, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, fontVariantNumeric: "tabular-nums" },
  inpText: { width: "100%", minWidth: 120, padding: "4px 6px", fontSize: 13, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4 },
  saveBtn: { padding: "6px 14px", fontSize: 12, fontWeight: 600, background: "var(--cyan)", color: "#000", border: "none", borderRadius: 4, minWidth: 90 },
  tdTotal: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "2px solid var(--border)" },
  tdTotalNum: { padding: "10px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
};
