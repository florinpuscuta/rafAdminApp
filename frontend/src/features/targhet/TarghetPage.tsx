import { useEffect, useMemo, useState } from "react";

import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { getTarghet, putGrowthPct } from "./api";
import type { TgtAgentRow, TgtMonthCell, TgtResponse, TgtScope } from "./types";

const MONTHS_RO = [
  "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];
const MONTH_ABBR = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];

type MonthMode = "ytd" | "all" | "custom";

function scopeFromCompany(c: CompanyScope): TgtScope {
  return c === "adeplast" ? "adp" : (c as TgtScope);
}

function scopeLabel(s: TgtScope): string {
  if (s === "adp") return "Adeplast";
  if (s === "sika") return "Sika";
  return "SIKADP";
}

function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtRo(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

function fmtSigned(n: number): string {
  const s = fmtRo(Math.abs(n));
  if (n > 0) return `+${s}`;
  if (n < 0) return `-${s}`;
  return s;
}

function achievementTone(pct: number): "green" | "orange" | "red" {
  if (pct >= 100) return "green";
  if (pct >= 50) return "orange";
  return "red";
}

function toneColor(tone: "green" | "orange" | "red"): string {
  if (tone === "green") return "var(--green)";
  if (tone === "orange") return "#d97706";
  return "var(--red)";
}

function toneBg(tone: "green" | "orange" | "red"): string {
  if (tone === "green") return "rgba(5, 150, 105, 0.15)";
  if (tone === "orange") return "rgba(217, 119, 6, 0.18)";
  return "rgba(220, 38, 38, 0.15)";
}

function chipWhite(active: boolean, color: string): React.CSSProperties {
  return {
    background: active ? color : "#fff",
    color: active ? "#fff" : color,
    border: `1px solid ${active ? color : color + "66"}`,
    borderRadius: 5, cursor: "pointer",
  };
}

export default function TarghetPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [data, setData] = useState<TgtResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Draft per-month pct editabil pe SIKADP (persistă la PUT → se aplică peste tot).
  const [pctDraft, setPctDraft] = useState<Record<number, string>>({});
  const [pctDirty, setPctDirty] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const canEditPct = apiScope === "sikadp";

  // Selectie luni
  const [monthMode, setMonthMode] = useState<MonthMode>("ytd");
  const [customMonths, setCustomMonths] = useState<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getTarghet({ scope: apiScope, year })
      .then((r) => {
        if (cancelled) return;
        setData(r);
        const draft: Record<number, string> = {};
        for (const it of r.growthPct) {
          draft[it.month] = String(toNum(it.pct));
        }
        setPctDraft(draft);
        setPctDirty(new Set());
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiScope, year]);

  // Map pct per lună — folosit pentru calcul grand filtrat.
  const pctByMonth = useMemo((): Map<number, number> => {
    const m = new Map<number, number>();
    if (!data) return m;
    for (const it of data.growthPct) {
      m.set(it.month, toNum(it.pct));
    }
    return m;
  }, [data]);

  function patchPct(month: number, value: string) {
    setPctDraft((prev) => ({ ...prev, [month]: value }));
    setPctDirty((prev) => new Set(prev).add(month));
  }

  async function saveAllPct() {
    if (pctDirty.size === 0) return;
    setSaving(true);
    setError(null);
    try {
      const items = Array.from(pctDirty).map((m) => ({
        month: m, pct: pctDraft[m] || "0",
      }));
      await putGrowthPct(year, items);
      // Reîncarcă targhetul cu noile procente aplicate.
      const fresh = await getTarghet({ scope: apiScope, year });
      setData(fresh);
      const draft: Record<number, string> = {};
      for (const it of fresh.growthPct) {
        draft[it.month] = String(toNum(it.pct));
      }
      setPctDraft(draft);
      setPctDirty(new Set());
      setFlash("Procente salvate");
      setTimeout(() => setFlash(null), 1500);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la salvare");
    } finally {
      setSaving(false);
    }
  }

  function applyAllMonths(value: string) {
    const next: Record<number, string> = {};
    const dirty = new Set<number>();
    for (let m = 1; m <= 12; m++) {
      next[m] = value;
      dirty.add(m);
    }
    setPctDraft(next);
    setPctDirty(dirty);
  }

  function toggleMonth(m: number) {
    setMonthMode("custom");
    setCustomMonths((s) => {
      const n = new Set(s);
      n.has(m) ? n.delete(m) : n.add(m);
      return n;
    });
  }

  // Luni YTD = luni cu date în year curent
  const ytdMonths = useMemo((): number[] => {
    if (!data) return [];
    return data.monthTotals
      .filter((mt) => toNum(mt.currSales) > 0)
      .map((mt) => mt.month);
  }, [data]);

  const activeMonths = useMemo((): Set<number> => {
    if (monthMode === "all") return new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    if (monthMode === "ytd") return new Set(ytdMonths);
    return customMonths;
  }, [monthMode, ytdMonths, customMonths]);

  // Grand totals recalculate pentru lunile active — target per lună cu pct-ul ei.
  const filteredGrand = useMemo(() => {
    if (!data) return null;
    let prevSales = 0, currSales = 0, target = 0;
    for (const mt of data.monthTotals) {
      if (!activeMonths.has(mt.month)) continue;
      const prev = toNum(mt.prevSales);
      const curr = toNum(mt.currSales);
      const pct = pctByMonth.get(mt.month) ?? 10;
      prevSales += prev;
      currSales += curr;
      target += prev * (100 + pct) / 100;
    }
    const gap = currSales - target;
    const achievementPct = target > 0 ? (currSales / target) * 100 : 0;
    return { currSales, target, gap, achievementPct, prevSales };
  }, [data, activeMonths, pctByMonth]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} — Targhet {data?.yearCurr ?? year} vs {data?.yearPrev ?? year - 1}
        </h1>
        <div style={styles.controls}>
          <YearSelector value={year} onChange={setYear} />
        </div>
      </div>

      {/* Month chip selector */}
      <div data-chipgrid="true" style={{
        display: "grid",
        gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
        gap: 5, marginBottom: 12,
      }}>
        <button
          type="button" data-compact="true"
          onClick={() => { setMonthMode("ytd"); setCustomMonths(new Set()); }}
          style={chipWhite(monthMode === "ytd", "#0ea5e9")}
        >YTD</button>
        <button
          type="button" data-compact="true"
          onClick={() => { setMonthMode("all"); setCustomMonths(new Set()); }}
          style={chipWhite(monthMode === "all", "#0ea5e9")}
        >Toate</button>
        <button
          type="button" data-compact="true"
          onClick={() => { setMonthMode("custom"); setCustomMonths(new Set()); }}
          style={chipWhite(monthMode === "custom" && customMonths.size === 0, "#ef4444")}
        >Nimic</button>
        {MONTH_ABBR.map((ab, i) => {
          const m = i + 1;
          const active = activeMonths.has(m);
          return (
            <button
              key={m} type="button" data-compact="true"
              onClick={() => toggleMonth(m)}
              style={chipWhite(active, "#22c55e")}
            >{ab}</button>
          );
        })}
      </div>

      {canEditPct && (
        <GrowthPctEditor
          draft={pctDraft}
          dirty={pctDirty}
          saving={saving}
          onPatch={patchPct}
          onSave={saveAllPct}
          onApplyAll={applyAllMonths}
        />
      )}

      {flash && <div style={styles.flash}>{flash}</div>}
      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {data && filteredGrand && (
        <>
          <div style={styles.kpiRow}>
            <KpiCard label="Realizat" value={fmtRo(filteredGrand.currSales)} />
            <KpiCard label="Target" value={fmtRo(filteredGrand.target)} />
            <KpiCard
              label="Gap"
              value={fmtSigned(filteredGrand.gap)}
              tone={filteredGrand.gap >= 0 ? "green" : "red"}
            />
            <KpiCard
              label="Achievement %"
              value={`${filteredGrand.achievementPct.toFixed(1)}%`}
              tone={achievementTone(filteredGrand.achievementPct)}
            />
          </div>

          <div className="agent-section">
            <AgentsTable
              agents={data.agents}
              activeMonths={activeMonths}
              pctByMonth={pctByMonth}
            />
          </div>
        </>
      )}
    </div>
  );
}

function GrowthPctEditor({
  draft, dirty, saving, onPatch, onSave, onApplyAll,
}: {
  draft: Record<number, string>;
  dirty: Set<number>;
  saving: boolean;
  onPatch: (month: number, value: string) => void;
  onSave: () => void;
  onApplyAll: (value: string) => void;
}) {
  const [bulk, setBulk] = useState("10");
  return (
    <div style={styles.pctEditor}>
      <div style={styles.pctRow}>
        <span style={styles.pctLabel}>% creștere / lună:</span>
        {MONTH_ABBR.map((ab, i) => {
          const m = i + 1;
          const isDirty = dirty.has(m);
          return (
            <label key={m} style={styles.pctCell}>
              <span style={styles.pctMonth}>{ab}</span>
              <input
                data-raw="true"
                type="number" step="0.5" min={-50} max={500}
                value={draft[m] ?? ""}
                onChange={(e) => onPatch(m, e.target.value)}
                style={{
                  ...styles.pctInput,
                  borderColor: isDirty ? "#eab308" : "var(--border)",
                  background: isDirty ? "rgba(234,179,8,0.08)" : "var(--bg-elevated)",
                }}
              />
            </label>
          );
        })}
      </div>
      <div style={styles.pctActions}>
        <label style={styles.bulkLabel}>
          Aplică la toate:
          <input
            data-raw="true"
            type="number" step="0.5" min={-50} max={500}
            value={bulk}
            onChange={(e) => setBulk(e.target.value)}
            style={{ ...styles.pctInput, width: 64 }}
          />
          <button
            data-wide="true" type="button"
            onClick={() => onApplyAll(bulk)}
            style={styles.bulkBtn}
          >Aplică</button>
        </label>
        <button
          data-wide="true" type="button"
          onClick={onSave}
          disabled={dirty.size === 0 || saving}
          style={{
            ...styles.saveBtn,
            opacity: dirty.size > 0 && !saving ? 1 : 0.5,
            cursor: dirty.size > 0 && !saving ? "pointer" : "default",
          }}
        >{saving ? "…" : `Salvează${dirty.size ? ` (${dirty.size})` : ""}`}</button>
      </div>
    </div>
  );
}

function YearSelector({ value, onChange }: { value: number; onChange: (y: number) => void }) {
  const current = new Date().getFullYear();
  const options = [current, current - 1, current - 2, current - 3];
  return (
    <select value={value} onChange={(e) => onChange(Number(e.target.value))} style={styles.yearSelect}>
      {options.map((y) => <option key={y} value={y}>{y}</option>)}
    </select>
  );
}

function KpiCard({ label, value, tone }: { label: string; value: string; tone?: "green" | "orange" | "red" }) {
  const col = tone ? toneColor(tone) : "var(--text)";
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color: col }}>{value}</div>
    </div>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  const tone = achievementTone(pct);
  const clamped = Math.max(0, Math.min(pct, 150));
  const widthPct = (clamped / 150) * 100;
  const color = toneColor(tone);
  const bg = toneBg(tone);
  return (
    <div style={{ ...styles.barOuter, background: bg }}>
      <div style={{ ...styles.barFill, width: `${widthPct}%`, background: color }} />
      <div style={styles.barLabel}>{pct.toFixed(0)}%</div>
    </div>
  );
}

function AgentsTable({
  agents, activeMonths, pctByMonth,
}: {
  agents: TgtAgentRow[];
  activeMonths: Set<number>;
  pctByMonth: Map<number, number>;
}) {
  const sortedMonths = Array.from(activeMonths).sort((a, b) => a - b);

  function filteredTotals(a: TgtAgentRow) {
    let prev = 0, curr = 0, target = 0;
    for (const mc of a.months) {
      if (!activeMonths.has(mc.month)) continue;
      const p = toNum(mc.prevSales);
      const c = toNum(mc.currSales);
      const pct = pctByMonth.get(mc.month) ?? 10;
      prev += p;
      curr += c;
      target += p * (100 + pct) / 100;
    }
    const gap = curr - target;
    const pct = target > 0 ? (curr / target) * 100 : 0;
    return { curr, target, gap, pct };
  }

  const monthCellMap = (a: TgtAgentRow): Map<number, TgtMonthCell> =>
    new Map(a.months.map((mc) => [mc.month, mc]));

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>
          Targhet per agent{sortedMonths.length < 12 && sortedMonths.length > 0
            ? ` — ${sortedMonths.map((m) => MONTHS_RO[m - 1]).join(", ")}`
            : " — 12 luni"}
        </h2>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.thAgent}>Agent</th>
              <th style={styles.thNum}>Realizat</th>
              <th style={styles.thNum}>Target</th>
              <th style={styles.thNum}>Gap</th>
              <th style={{ ...styles.thNum, minWidth: 150 }}>Achievement</th>
              {sortedMonths.map((m) => (
                <th key={m} style={styles.thMonth}>
                  {MONTHS_RO[m - 1]}
                  <div style={styles.thMonthPct}>
                    {(pctByMonth.get(m) ?? 10).toFixed(0)}%
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => {
              const { curr, target, gap, pct } = filteredTotals(a);
              const cellMap = monthCellMap(a);
              return (
                <tr key={a.agentId ?? a.agentName}>
                  <td style={styles.tdAgent}>{a.agentName}</td>
                  <td style={styles.tdNum}>{fmtRo(curr)}</td>
                  <td style={styles.tdNum}>{fmtRo(target)}</td>
                  <td style={{
                    ...styles.tdNum,
                    color: gap >= 0 ? "var(--green)" : "var(--red)",
                    fontWeight: 600,
                  }}>
                    {fmtSigned(gap)}
                  </td>
                  <td style={styles.tdNum}>
                    <ProgressBar pct={pct} />
                  </td>
                  {sortedMonths.map((m) => {
                    const mc = cellMap.get(m);
                    if (!mc) return <td key={m} style={styles.tdMonth}>—</td>;
                    const t = toNum(mc.target);
                    const c = toNum(mc.currSales);
                    if (t === 0 && c === 0) return <td key={m} style={styles.tdMonth}>—</td>;
                    const p = t > 0 ? (c / t) * 100 : 0;
                    const tone = achievementTone(p);
                    return (
                      <td key={m} style={{
                        ...styles.tdMonth,
                        color: toneColor(tone),
                        fontWeight: 600,
                      }} title={`Target: ${fmtRo(t)} · Realizat: ${fmtRo(c)}`}>
                        {p.toFixed(0)}%
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 12px", color: "var(--text)" },
  headerRow: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    gap: 12, marginBottom: 12, flexWrap: "wrap",
  },
  title: {
    margin: 0, fontSize: 17, fontWeight: 600, color: "var(--text)",
    letterSpacing: -0.2,
  },
  controls: { display: "flex", alignItems: "center", gap: 12 },
  pctEditor: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: "10px 12px", marginBottom: 12,
    display: "flex", flexDirection: "column", gap: 8,
  },
  pctRow: {
    display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
  },
  pctLabel: {
    fontSize: 12, color: "var(--muted)", fontWeight: 600,
    textTransform: "uppercase", letterSpacing: 0.4, marginRight: 6,
  },
  pctCell: {
    display: "flex", flexDirection: "column", alignItems: "center",
    gap: 2,
  },
  pctMonth: {
    fontSize: 10, color: "var(--muted)", textTransform: "uppercase",
    letterSpacing: 0.3, fontWeight: 600,
  },
  pctInput: {
    width: 52, padding: "4px 6px", fontSize: 12,
    background: "var(--bg-elevated)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 5, textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  pctActions: {
    display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  bulkLabel: {
    display: "flex", alignItems: "center", gap: 6,
    fontSize: 12, color: "var(--muted)",
  },
  bulkBtn: {
    padding: "5px 12px", fontSize: 11, fontWeight: 600,
    background: "var(--bg-elevated)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 5, cursor: "pointer",
  },
  saveBtn: {
    padding: "6px 16px", fontSize: 12, fontWeight: 600,
    background: "var(--cyan)", color: "#000",
    border: "none", borderRadius: 5,
  },
  yearSelect: {
    padding: "7px 12px", fontSize: 13,
    background: "var(--bg-elevated)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer",
  },
  error: {
    color: "var(--red)", padding: 12,
    background: "rgba(220, 38, 38, 0.08)", borderRadius: 6, marginBottom: 12,
  },
  flash: {
    padding: "8px 12px", background: "rgba(34,197,94,0.1)",
    border: "1px solid rgba(34,197,94,0.4)", color: "#86efac",
    borderRadius: 6, fontSize: 12, marginBottom: 12,
  },
  loading: { color: "var(--muted)", padding: 12 },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 10, marginBottom: 14,
  },
  kpiCard: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: "8px 10px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
    display: "flex", flexDirection: "column", justifyContent: "center",
    minHeight: 58,
  },
  kpiLabel: {
    fontSize: 10, fontWeight: 600, textTransform: "uppercase",
    color: "var(--muted)", letterSpacing: 0.4, marginBottom: 2,
    lineHeight: 1.2,
  },
  kpiValue: {
    fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums",
    lineHeight: 1.15,
  },
  card: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: 16, marginBottom: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  cardHeader: { marginBottom: 12 },
  cardTitle: {
    margin: 0, fontSize: 14, fontWeight: 600, color: "var(--text)",
    letterSpacing: 0.1,
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  thAgent: {
    textAlign: "left", padding: "6px 8px",
    fontSize: 10.5, fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4, textTransform: "uppercase", whiteSpace: "nowrap",
    position: "sticky", left: 0, background: "var(--card)", zIndex: 1,
  },
  thNum: {
    textAlign: "right", padding: "6px 8px",
    fontSize: 10.5, fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4, textTransform: "uppercase", whiteSpace: "nowrap",
  },
  thMonth: {
    textAlign: "center", padding: "6px 6px",
    fontSize: 10.5, fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4, textTransform: "uppercase",
    whiteSpace: "nowrap", minWidth: 44,
  },
  thMonthPct: {
    fontSize: 9, fontWeight: 500, color: "var(--cyan)",
    letterSpacing: 0, textTransform: "none", marginTop: 1,
  },
  tdAgent: {
    padding: "7px 8px", fontSize: 13, color: "var(--text)",
    borderBottom: "1px solid var(--border)", whiteSpace: "nowrap",
    position: "sticky", left: 0, background: "var(--card)", zIndex: 1,
    fontWeight: 500,
  },
  tdNum: {
    padding: "7px 8px", fontSize: 13, color: "var(--text)",
    borderBottom: "1px solid var(--border)", textAlign: "right",
    fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap",
  },
  tdMonth: {
    padding: "7px 6px", fontSize: 12, textAlign: "center",
    borderBottom: "1px solid var(--border)",
    fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap",
  },
  barOuter: {
    position: "relative", height: 18, borderRadius: 4, overflow: "hidden",
    minWidth: 130,
  },
  barFill: {
    position: "absolute", left: 0, top: 0, bottom: 0,
    transition: "width .2s",
  },
  barLabel: {
    position: "relative", zIndex: 1, fontSize: 11, fontWeight: 700,
    color: "var(--text)", textAlign: "center", lineHeight: "18px",
    mixBlendMode: "difference",
  },
};
