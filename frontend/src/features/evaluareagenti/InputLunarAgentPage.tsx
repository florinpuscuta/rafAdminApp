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
      + toNum(src.merchandiserZona)
      + toNum(src.cheltuieliAuto)
      + toNum(src.alteCheltuieli)
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
        merchandiserZona: row.merchandiserZona || "0",
        cheltuieliAuto: row.cheltuieliAuto || "0",
        alteCheltuieli: row.alteCheltuieli || "0",
        alteCheltuieliLabel: row.alteCheltuieliLabel,
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
    acc.merchandiserZona += toNum(src.merchandiserZona);
    acc.cheltuieliAuto += toNum(src.cheltuieliAuto);
    acc.alteCheltuieli += toNum(src.alteCheltuieli);
    acc.bonusRaion += toNum(src.bonusRaion);
    acc.total += previewTotal(r);
    return acc;
  }, {
    vanzari: 0, salariuFix: 0, bonusAgent: 0, merchandiserZona: 0,
    cheltuieliAuto: 0, alteCheltuieli: 0, bonusRaion: 0, total: 0,
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
                <th style={styles.th}>Merchandiser zonă</th>
                <th style={styles.th}>Cheltuieli auto</th>
                <th style={styles.th}>Alte cheltuieli</th>
                <th style={styles.thLeft}>Etichetă</th>
                <th style={styles.th}>Bonus zonă</th>
                <th style={styles.th}>TOTAL</th>
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
                        value={valueOf(r, "merchandiserZona")}
                        onChange={(e) => patch(r.agentId, "merchandiserZona", e.target.value)}
                      />
                    </td>
                    <td style={styles.td}>
                      <input
                        data-raw="true"
                        type="number" step="0.01"
                        style={styles.inpNum}
                        value={valueOf(r, "cheltuieliAuto")}
                        onChange={(e) => patch(r.agentId, "cheltuieliAuto", e.target.value)}
                      />
                    </td>
                    <td style={styles.td}>
                      <input
                        data-raw="true"
                        type="number" step="0.01"
                        style={styles.inpNum}
                        value={valueOf(r, "alteCheltuieli")}
                        onChange={(e) => patch(r.agentId, "alteCheltuieli", e.target.value)}
                      />
                    </td>
                    <td style={styles.tdLeft}>
                      <input
                        data-raw="true"
                        type="text"
                        style={styles.inpLabel}
                        value={valueOf(r, "alteCheltuieliLabel")}
                        onChange={(e) => patch(r.agentId, "alteCheltuieliLabel", e.target.value)}
                        placeholder="ex: Cadouri"
                      />
                    </td>
                    <td style={styles.tdRoRight}>{fmtRo(toNum(r.bonusRaion), 0)}</td>
                    <td style={{ ...styles.td, fontWeight: 700, color: "var(--cyan)" }}>
                      {fmtRo(total, 0)}
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
                <td style={styles.tdTotalNum}>{fmtRo(totals.merchandiserZona, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.cheltuieliAuto, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.alteCheltuieli, 0)}</td>
                <td style={styles.tdTotal}></td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.bonusRaion, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.total, 0)}</td>
                <td style={styles.tdTotal}></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "12px 8px", width: "100%" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 10, flexWrap: "wrap" },
  title: { fontSize: 18, fontWeight: 700, color: "var(--cyan)", margin: "0 0 2px" },
  lead: { color: "var(--muted)", fontSize: 11, margin: 0, maxWidth: 720, lineHeight: 1.4 },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "6px 10px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  flash: { padding: "6px 10px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.4)", color: "#86efac", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12, tableLayout: "auto" },
  th: { padding: "8px 4px", textAlign: "right", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thLeft: { padding: "8px 8px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  td: { padding: "4px 4px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdRoRight: { padding: "4px 4px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", color: "var(--muted)" },
  tdLeft: { padding: "4px 8px", textAlign: "left", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" },
  rowDirty: { background: "rgba(234,179,8,0.06)" },
  inpNum: { width: "100%", maxWidth: 80, minWidth: 0, padding: "3px 4px", textAlign: "right", fontSize: 12, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, fontVariantNumeric: "tabular-nums", boxSizing: "border-box" },
  inpLabel: { width: "100%", maxWidth: 110, minWidth: 0, padding: "3px 4px", fontSize: 11, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, boxSizing: "border-box" },
  saveBtn: { padding: "4px 10px", fontSize: 11, fontWeight: 600, background: "var(--cyan)", color: "#000", border: "none", borderRadius: 4, minWidth: 72 },
  tdTotal: { padding: "8px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "2px solid var(--border)" },
  tdTotalNum: { padding: "8px 4px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
};
