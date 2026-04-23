import { Fragment, useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getZonaAgentDetail, getZonaAgents, upsertZonaBonus } from "./api";
import { MonthYearPicker, fmtRo, toNum, useEvaluareYearMonth } from "./shared";
import type {
  ZonaAgentDetail,
  ZonaAgentSummary,
  ZonaAgentsResponse,
  ZonaStoreRow,
} from "./types";

/**
 * Zona Agent — listă agenți SIKADP; click pe agent → magazinele se desfac
 * inline sub acel rând (accordion). Bonus manual per magazin;
 * suma bonusurilor → "Bonus zonă" în matricea lunară.
 */
export default function ZonaAgentPage() {
  const { year, month, setYearMonth } = useEvaluareYearMonth();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [details, setDetails] = useState<Record<string, ZonaAgentDetail>>({});
  const [loadingDetail, setLoadingDetail] = useState<Set<string>>(new Set());

  const [data, setData] = useState<ZonaAgentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setExpanded(new Set());
    setDetails({});
    try {
      setData(await getZonaAgents(year, month));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => { void load(); }, [load]);

  const toggleAgent = async (agentId: string) => {
    const next = new Set(expanded);
    if (next.has(agentId)) {
      next.delete(agentId);
      setExpanded(next);
      return;
    }
    next.add(agentId);
    setExpanded(next);
    if (!details[agentId]) {
      setLoadingDetail((prev) => new Set(prev).add(agentId));
      try {
        const d = await getZonaAgentDetail(agentId, year, month);
        setDetails((prev) => ({ ...prev, [agentId]: d }));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
      } finally {
        setLoadingDetail((prev) => {
          const n = new Set(prev);
          n.delete(agentId);
          return n;
        });
      }
    }
  };

  const handleSaved = (agentId: string, updated: ZonaStoreRow) => {
    setDetails((prev) => {
      const d = prev[agentId];
      if (!d) return prev;
      const stores = d.stores.map((x) => x.storeId === updated.storeId ? updated : x);
      const totalBonus = stores.reduce((s, x) => s + toNum(x.bonus), 0);
      return { ...prev, [agentId]: { ...d, stores, totalBonus: String(totalBonus) } };
    });
    setData((prev) => {
      if (!prev) return prev;
      const bonusDelta = toNum(updated.bonus);
      const agents = prev.agents.map((a) => {
        if (a.agentId !== agentId) return a;
        const currentStore = details[agentId]?.stores.find((s) => s.storeId === updated.storeId);
        const prevBonus = currentStore ? toNum(currentStore.bonus) : 0;
        const newTotal = toNum(a.totalBonus) - prevBonus + bonusDelta;
        return { ...a, totalBonus: String(newTotal) };
      });
      return { ...prev, agents };
    });
  };

  const sortedAgents = useMemo<ZonaAgentSummary[]>(() => {
    if (!data) return [];
    return [...data.agents].sort(
      (a, b) => toNum(b.totalRealizat) - toNum(a.totalRealizat),
    );
  }, [data]);

  const grand = useMemo(() => {
    if (!data) return { target: 0, realizat: 0, bonus: 0 };
    return data.agents.reduce(
      (acc, a) => ({
        target: acc.target + toNum(a.totalTarget),
        realizat: acc.realizat + toNum(a.totalRealizat),
        bonus: acc.bonus + toNum(a.totalBonus),
      }),
      { target: 0, realizat: 0, bonus: 0 },
    );
  }, [data]);

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Zona Agent</h1>
          <p style={styles.lead}>
            Click pe un agent pentru a desface magazinele lui. Bonus manual
            per magazin — suma devine "Bonus zonă" în matricea lunară.
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
      ) : !data || data.agents.length === 0 ? (
        <div style={styles.muted}>Nu există agenți activi.</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.thLeft}>Agent</th>
                <th style={styles.th}>Magazine</th>
                <th style={styles.th}>Target</th>
                <th style={styles.th}>Realizat</th>
                <th style={styles.th}>%</th>
                <th style={styles.th}>Bonus total</th>
              </tr>
            </thead>
            <tbody>
              {sortedAgents.map((a: ZonaAgentSummary) => {
                const tgt = toNum(a.totalTarget);
                const rz = toNum(a.totalRealizat);
                const ach = tgt > 0 ? (rz / tgt) * 100 : null;
                const isOpen = expanded.has(a.agentId);
                const isLoading = loadingDetail.has(a.agentId);
                const detail = details[a.agentId];
                return (
                  <Fragment key={a.agentId}>
                    <tr
                      onClick={() => void toggleAgent(a.agentId)}
                      style={{ ...styles.rowClick, ...(isOpen ? styles.rowOpen : {}) }}
                    >
                      <td style={styles.tdLeft}>
                        <span style={{ ...styles.chev, transform: isOpen ? "rotate(90deg)" : "none" }}>
                          ›
                        </span>
                        {a.agentName}
                      </td>
                      <td style={styles.td}>{a.storeCount}</td>
                      <td style={styles.td}>{fmtRo(tgt, 0)}</td>
                      <td style={styles.td}>{fmtRo(rz, 0)}</td>
                      <td style={{ ...styles.td, color: ach == null ? "var(--muted)" : colorForPct(ach) }}>
                        {ach == null ? "—" : `${fmtRo(ach, 1)}%`}
                      </td>
                      <td style={{ ...styles.td, fontWeight: 700, color: "var(--cyan)" }}>
                        {fmtRo(toNum(a.totalBonus), 0)}
                      </td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={6} style={styles.expandCell}>
                          {isLoading || !detail ? (
                            <div style={styles.mutedSmall}>Se încarcă magazinele…</div>
                          ) : (
                            <StoresBlock
                              agentId={a.agentId}
                              detail={detail}
                              year={year}
                              month={month}
                              onSaved={(row) => handleSaved(a.agentId, row)}
                            />
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
              <tr>
                <td style={styles.tdTotal}>TOTAL</td>
                <td style={styles.tdTotal}></td>
                <td style={styles.tdTotalNum}>{fmtRo(grand.target, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(grand.realizat, 0)}</td>
                <td style={styles.tdTotal}></td>
                <td style={styles.tdTotalNum}>{fmtRo(grand.bonus, 0)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ───────────────── Magazine (inline) ─────────────────

function StoresBlock({
  agentId, detail, year, month, onSaved,
}: {
  agentId: string;
  detail: ZonaAgentDetail;
  year: number;
  month: number;
  onSaved: (updated: ZonaStoreRow) => void;
}) {
  const [dirty, setDirty] = useState<Record<string, { bonus: string; note: string | null }>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const patch = (storeId: string, field: "bonus" | "note", value: string) => {
    setDirty((prev) => {
      const orig = detail.stores.find((s) => s.storeId === storeId);
      if (!orig) return prev;
      const base = prev[storeId] ?? { bonus: orig.bonus, note: orig.note };
      const next = { ...base, [field]: value };
      return { ...prev, [storeId]: next };
    });
  };

  const valueOf = (s: ZonaStoreRow, field: "bonus" | "note"): string => {
    const d = dirty[s.storeId];
    if (d) return field === "bonus" ? d.bonus : (d.note ?? "");
    return field === "bonus" ? s.bonus : (s.note ?? "");
  };

  const save = async (s: ZonaStoreRow) => {
    const d = dirty[s.storeId];
    if (!d) return;
    setSavingId(s.storeId);
    setErr(null);
    try {
      const updated = await upsertZonaBonus({
        agentId, storeId: s.storeId, year, month,
        bonus: d.bonus || "0",
        note: d.note,
      });
      onSaved(updated);
      setDirty((prev) => {
        const next = { ...prev };
        delete next[s.storeId];
        return next;
      });
      setFlash(`Salvat: ${s.storeName}`);
      setTimeout(() => setFlash(null), 1500);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Eroare la salvare");
    } finally {
      setSavingId(null);
    }
  };

  if (detail.stores.length === 0) {
    return (
      <div style={styles.mutedSmall}>
        Agentul nu are magazine alocate. Alocă din Settings → Mapări.
      </div>
    );
  }

  return (
    <div>
      {err && <div style={styles.error}>{err}</div>}
      {flash && <div style={styles.flash}>{flash}</div>}
      <table style={styles.innerTable}>
        <thead>
          <tr>
            <th style={styles.innerThLeft}>Magazin</th>
            <th style={styles.innerTh}>Target</th>
            <th style={styles.innerTh}>Realizat</th>
            <th style={styles.innerTh}>%</th>
            <th style={styles.innerTh}>Bonus (RON)</th>
            <th style={styles.innerThLeft}>Note</th>
            <th style={styles.innerTh}></th>
          </tr>
        </thead>
        <tbody>
          {detail.stores.map((s) => {
            const ach = s.achievementPct == null ? null : toNum(s.achievementPct);
            const isDirty = Boolean(dirty[s.storeId]);
            const isSaving = savingId === s.storeId;
            return (
              <tr key={s.storeId} style={isDirty ? styles.rowDirty : undefined}>
                <td style={styles.innerTdLeft}>{s.storeName}</td>
                <td style={styles.innerTd}>{fmtRo(toNum(s.target), 0)}</td>
                <td style={styles.innerTd}>{fmtRo(toNum(s.realizat), 0)}</td>
                <td style={{ ...styles.innerTd, color: ach == null ? "var(--muted)" : colorForPct(ach) }}>
                  {ach == null ? "—" : `${fmtRo(ach, 1)}%`}
                </td>
                <td style={styles.innerTd}>
                  <input
                    data-raw="true"
                    type="number" step="0.01"
                    style={styles.inpNum}
                    value={valueOf(s, "bonus")}
                    onChange={(e) => patch(s.storeId, "bonus", e.target.value)}
                  />
                </td>
                <td style={styles.innerTdLeft}>
                  <input
                    data-raw="true"
                    type="text"
                    style={styles.inpText}
                    value={valueOf(s, "note")}
                    onChange={(e) => patch(s.storeId, "note", e.target.value)}
                    placeholder="—"
                  />
                </td>
                <td style={styles.innerTd}>
                  <button
                    data-wide="true"
                    onClick={() => save(s)}
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
            <td style={styles.innerTotal}>TOTAL</td>
            <td style={styles.innerTotalNum}>{fmtRo(toNum(detail.totalTarget), 0)}</td>
            <td style={styles.innerTotalNum}>{fmtRo(toNum(detail.totalRealizat), 0)}</td>
            <td style={styles.innerTotal}></td>
            <td style={styles.innerTotalNum}>{fmtRo(toNum(detail.totalBonus), 0)}</td>
            <td style={styles.innerTotal} colSpan={2}></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function colorForPct(pct: number): string {
  if (pct >= 100) return "#4ade80";
  if (pct >= 80) return "#fbbf24";
  return "#ef4444";
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "12px 8px", width: "100%" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 10, flexWrap: "wrap" },
  title: { fontSize: 18, fontWeight: 700, color: "var(--cyan)", margin: "0 0 2px" },
  lead: { color: "var(--muted)", fontSize: 11, margin: 0, maxWidth: 640, lineHeight: 1.4 },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  mutedSmall: { color: "var(--muted)", fontSize: 12, padding: "6px 4px" },
  error: { padding: "6px 10px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  flash: { padding: "6px 10px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.4)", color: "#86efac", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: { padding: "8px 6px", textAlign: "right", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thLeft: { padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  td: { padding: "6px 6px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { padding: "6px 10px", textAlign: "left", borderBottom: "1px solid var(--border)", fontWeight: 600 },
  rowClick: { cursor: "pointer" },
  rowOpen: { background: "rgba(34,211,238,0.04)" },
  rowDirty: { background: "rgba(234,179,8,0.06)" },
  chev: { display: "inline-block", color: "var(--muted)", fontSize: 14, marginRight: 6, transition: "transform 120ms ease" },
  expandCell: { padding: "6px 8px 10px 20px", background: "rgba(0,0,0,0.15)", borderBottom: "1px solid var(--border)" },
  innerTable: { width: "100%", borderCollapse: "collapse", fontSize: 11, background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 6 },
  innerTh: { padding: "6px 4px", textAlign: "right", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", textTransform: "uppercase", letterSpacing: "0.04em" },
  innerThLeft: { padding: "6px 8px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", textTransform: "uppercase", letterSpacing: "0.04em" },
  innerTd: { padding: "4px 4px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  innerTdLeft: { padding: "4px 8px", textAlign: "left", borderBottom: "1px solid var(--border)" },
  innerTotal: { padding: "6px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "1px solid var(--border)" },
  innerTotalNum: { padding: "6px 4px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "1px solid var(--border)" },
  inpNum: { width: 90, padding: "3px 4px", textAlign: "right", fontSize: 11, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, fontVariantNumeric: "tabular-nums", boxSizing: "border-box" },
  inpText: { width: "100%", minWidth: 0, padding: "3px 4px", fontSize: 11, background: "var(--bg)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4, boxSizing: "border-box" },
  saveBtn: { padding: "3px 8px", fontSize: 10, fontWeight: 600, background: "var(--cyan)", color: "#000", border: "none", borderRadius: 4, minWidth: 64 },
  tdTotal: { padding: "8px 10px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "2px solid var(--border)" },
  tdTotalNum: { padding: "8px 6px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
};
