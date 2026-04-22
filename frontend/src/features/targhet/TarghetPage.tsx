import { useEffect, useMemo, useState } from "react";

import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { getTarghet } from "./api";
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
  const [targetPct, setTargetPct] = useState<number>(10);
  const [pctDraft, setPctDraft] = useState<string>("10");
  const [data, setData] = useState<TgtResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selectie luni
  const [monthMode, setMonthMode] = useState<MonthMode>("ytd");
  const [customMonths, setCustomMonths] = useState<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getTarghet({ scope: apiScope, year, targetPct })
      .then((r) => { if (!cancelled) setData(r); })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiScope, year, targetPct]);

  function applyPct() {
    const v = Number(pctDraft);
    if (Number.isFinite(v)) setTargetPct(v);
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

  // Grand totals recalculate pentru lunile active
  const filteredGrand = useMemo(() => {
    if (!data) return null;
    const multiplier = (100 + targetPct) / 100;
    let prevSales = 0, currSales = 0;
    for (const mt of data.monthTotals) {
      if (!activeMonths.has(mt.month)) continue;
      prevSales += toNum(mt.prevSales);
      currSales += toNum(mt.currSales);
    }
    const target = prevSales * multiplier;
    const gap = currSales - target;
    const achievementPct = target > 0 ? (currSales / target) * 100 : 0;
    return { currSales, target, gap, achievementPct };
  }, [data, activeMonths, targetPct]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} — Targhet {data?.yearCurr ?? year} vs {data?.yearPrev ?? year - 1}
        </h1>
        <div style={styles.controls}>
          <label style={styles.ctrlLabel}>
            % creștere:
            <input
              type="number"
              value={pctDraft}
              onChange={(e) => setPctDraft(e.target.value)}
              onBlur={applyPct}
              onKeyDown={(e) => { if (e.key === "Enter") applyPct(); }}
              step={1} min={-50} max={500}
              style={styles.pctInput}
            />
            <span style={{ color: "var(--muted)" }}>%</span>
          </label>
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

          <AgentsTable
            agents={data.agents}
            activeMonths={activeMonths}
            targetPct={targetPct}
          />
        </>
      )}
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
  agents, activeMonths, targetPct,
}: {
  agents: TgtAgentRow[];
  activeMonths: Set<number>;
  targetPct: number;
}) {
  const sortedMonths = Array.from(activeMonths).sort((a, b) => a - b);
  const multiplier = (100 + targetPct) / 100;

  function filteredTotals(a: TgtAgentRow) {
    let prev = 0, curr = 0;
    for (const mc of a.months) {
      if (!activeMonths.has(mc.month)) continue;
      prev += toNum(mc.prevSales);
      curr += toNum(mc.currSales);
    }
    const target = prev * multiplier;
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
                <th key={m} style={styles.thMonth}>{MONTHS_RO[m - 1]}</th>
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
  ctrlLabel: {
    display: "flex", alignItems: "center", gap: 6,
    fontSize: 13, color: "var(--muted)",
  },
  pctInput: {
    width: 64, padding: "6px 8px", fontSize: 13,
    background: "var(--bg-elevated)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 6, textAlign: "right",
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
