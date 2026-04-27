import { useEffect, useMemo, useState } from "react";

import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { getBonusari } from "./api";
import type { BonAgentRow, BonMonthCell, BonResponse, BonScope } from "./types";

const MONTHS_RO = [
  "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];
const MONTH_ABBR = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];

type MonthMode = "ytd" | "all" | "custom";

function scopeFromCompany(c: CompanyScope): BonScope {
  return c === "adeplast" ? "adp" : (c as BonScope);
}

function scopeLabel(s: BonScope): string {
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

function growthTone(pct: number): "green" | "orange" | "red" {
  if (pct >= 1) return "green";
  if (pct >= -5) return "orange";
  return "red";
}

function toneColor(tone: "green" | "orange" | "red"): string {
  if (tone === "green") return "var(--green)";
  if (tone === "orange") return "#d97706";
  return "var(--red)";
}

function chipWhite(active: boolean, color: string): React.CSSProperties {
  return {
    background: active ? color : "#fff",
    color: active ? "#fff" : color,
    border: `1px solid ${active ? color : color + "66"}`,
    borderRadius: 5, cursor: "pointer",
  };
}

export default function BonusariPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [data, setData] = useState<BonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [monthMode, setMonthMode] = useState<MonthMode>("ytd");
  const [customMonths, setCustomMonths] = useState<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getBonusari({ scope: apiScope, year })
      .then((r) => { if (!cancelled) setData(r); })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiScope, year]);

  function toggleMonth(m: number) {
    setMonthMode("custom");
    setCustomMonths((s) => {
      const n = new Set(s);
      n.has(m) ? n.delete(m) : n.add(m);
      return n;
    });
  }

  // YTD = lunile 1..currentMonthLimit (luni cu date)
  const ytdMonths = useMemo((): number[] => {
    if (!data) return [];
    return Array.from({ length: data.currentMonthLimit }, (_, i) => i + 1);
  }, [data]);

  const activeMonths = useMemo((): Set<number> => {
    if (monthMode === "all") return new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    if (monthMode === "ytd") return new Set(ytdMonths);
    return customMonths;
  }, [monthMode, ytdMonths, customMonths]);

  // Grand total filtrat pentru lunile active
  const filteredGrandTotal = useMemo(() => {
    if (!data) return 0;
    return data.monthTotals
      .filter((mt) => activeMonths.has(mt.month))
      .reduce((s, mt) => s + toNum(mt.total), 0);
  }, [data, activeMonths]);

  const eligibleAgents = useMemo(() => {
    if (!data) return 0;
    return data.agents.filter((a) =>
      a.months.some((mc) => activeMonths.has(mc.month) && toNum(mc.total) > 0)
    ).length;
  }, [data, activeMonths]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} — Bonusări {data?.yearCurr ?? year}
        </h1>
        <YearSelector value={year} onChange={setYear} />
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
          const isFuture = data ? m > data.currentMonthLimit : false;
          return (
            <button
              key={m} type="button" data-compact="true"
              onClick={() => toggleMonth(m)}
              style={{
                ...chipWhite(active, "#22c55e"),
                opacity: isFuture ? 0.4 : 1,
              }}
            >{ab}</button>
          );
        })}
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {data && (
        <>
          <div className="agent-section">
            <RulesCard data={data} />
          </div>
          <div className="agent-section" style={styles.kpiRow}>
            <KpiCard
              label="Total bonus"
              value={`${fmtRo(filteredGrandTotal)} lei`}
              tone="green"
            />
            <KpiCard
              label="Agenți eligibili"
              value={String(eligibleAgents)}
            />
            <KpiCard
              label="Luni selectate"
              value={`${activeMonths.size} / 12`}
            />
          </div>

          <div className="agent-section">
            <AgentsTable
              agents={data.agents}
              activeMonths={activeMonths}
              currentMonthLimit={data.currentMonthLimit}
            />
          </div>
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

function RulesCard({ data }: { data: BonResponse }) {
  return (
    <div style={styles.rulesCard}>
      <div style={styles.rulesTitle}>Reguli</div>
      <div style={styles.rulesBody}>
        {data.rules.tiers.map((t) => (
          <span key={t.thresholdPct} style={styles.ruleChip}>
            <strong style={{ color: "var(--green)" }}>≥ +{toNum(t.thresholdPct)}%</strong>
            <span style={{ color: "var(--muted)" }}>→</span>
            <span style={{ fontWeight: 600 }}>{fmtRo(toNum(t.amount))} lei</span>
          </span>
        ))}
        <span style={{ ...styles.ruleChip, borderStyle: "dashed" }}>
          <span style={{ color: "var(--muted)" }}>Recuperare:</span>
          <span style={{ fontWeight: 600 }}>+{fmtRo(toNum(data.rules.recoveryAmount))} lei</span>
          <span style={{ color: "var(--muted)" }}>
            (dacă cumulat ≥ +{toNum(data.rules.recoveryThresholdPct)}%)
          </span>
        </span>
      </div>
    </div>
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

function AgentsTable({
  agents, activeMonths, currentMonthLimit,
}: {
  agents: BonAgentRow[];
  activeMonths: Set<number>;
  currentMonthLimit: number;
}) {
  const sortedMonths = Array.from(activeMonths).sort((a, b) => a - b);

  function filteredTotal(a: BonAgentRow): number {
    return a.months
      .filter((mc) => activeMonths.has(mc.month))
      .reduce((s, mc) => s + toNum(mc.total), 0);
  }

  const cellMap = (a: BonAgentRow): Map<number, BonMonthCell> =>
    new Map(a.months.map((mc) => [mc.month, mc]));

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>
          Bonus per agent{sortedMonths.length < 12 && sortedMonths.length > 0
            ? ` — ${sortedMonths.map((m) => MONTHS_RO[m - 1]).join(", ")}`
            : " — 12 luni"}
        </h2>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.thAgent}>Agent</th>
              <th style={styles.thNum}>Total bonus</th>
              {sortedMonths.map((m) => (
                <th key={m} style={{
                  ...styles.thMonth,
                  opacity: m > currentMonthLimit ? 0.4 : 1,
                }}>
                  {MONTHS_RO[m - 1]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => {
              const total = filteredTotal(a);
              const map = cellMap(a);
              return (
                <tr key={a.agentId ?? a.agentName}>
                  <td style={styles.tdAgent}>{a.agentName}</td>
                  <td style={{
                    ...styles.tdNum,
                    color: total > 0 ? "var(--green)" : "var(--muted)",
                    fontWeight: 700,
                  }}>
                    {total > 0 ? `${fmtRo(total)} lei` : "—"}
                  </td>
                  {sortedMonths.map((m) => {
                    const mc = map.get(m);
                    if (!mc) return <td key={m} style={styles.tdMonth}>—</td>;
                    return (
                      <td
                        key={m}
                        style={{ ...styles.tdMonth, opacity: mc.isFuture ? 0.35 : 1 }}
                        title={
                          mc.isFuture
                            ? "Lună viitoare"
                            : `Prev: ${fmtRo(toNum(mc.prevSales))} · Curr: ${fmtRo(toNum(mc.currSales))} · ` +
                              `Growth: ${toNum(mc.growthPct).toFixed(1)}% · ` +
                              `Bonus: ${fmtRo(toNum(mc.bonus))}` +
                              (toNum(mc.recovery) > 0 ? ` + Recup: ${fmtRo(toNum(mc.recovery))}` : "")
                        }
                      >
                        <MonthCellContent
                          bonus={toNum(mc.bonus)}
                          recovery={toNum(mc.recovery)}
                          growthPct={toNum(mc.growthPct)}
                          isFuture={mc.isFuture}
                        />
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

function MonthCellContent({
  bonus, recovery, growthPct, isFuture,
}: { bonus: number; recovery: number; growthPct: number; isFuture: boolean }) {
  if (isFuture) return <span style={{ color: "var(--muted)" }}>—</span>;
  const total = bonus + recovery;
  if (total === 0) {
    return (
      <span style={{ color: toneColor(growthTone(growthPct)), fontSize: 11 }}>
        {growthPct >= 0 ? "+" : ""}{growthPct.toFixed(1)}%
      </span>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <span style={{ color: "var(--green)", fontWeight: 700 }}>{fmtRo(bonus)}</span>
      {recovery > 0 && (
        <span style={{ color: "#2563eb", fontSize: 10, fontWeight: 600 }}>
          +{fmtRo(recovery)}
        </span>
      )}
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
  rulesCard: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: "10px 14px", marginBottom: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  rulesTitle: {
    fontSize: 10.5, fontWeight: 600, textTransform: "uppercase",
    color: "var(--muted)", letterSpacing: 0.4, marginBottom: 6,
  },
  rulesBody: {
    display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: 12,
  },
  ruleChip: {
    display: "inline-flex", alignItems: "center", gap: 6,
    padding: "3px 10px", borderRadius: 999,
    border: "1px solid var(--border)", background: "var(--bg-elevated)",
    color: "var(--text)",
  },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
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
    color: "var(--muted)", letterSpacing: 0.4, marginBottom: 2, lineHeight: 1.2,
  },
  kpiValue: {
    fontSize: 18, fontWeight: 700, fontVariantNumeric: "tabular-nums", lineHeight: 1.15,
  },
  card: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: 16, marginBottom: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  cardHeader: { marginBottom: 12 },
  cardTitle: {
    margin: 0, fontSize: 14, fontWeight: 600, color: "var(--text)", letterSpacing: 0.1,
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
    whiteSpace: "nowrap", minWidth: 56,
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
    padding: "6px 6px", fontSize: 12, textAlign: "center",
    borderBottom: "1px solid var(--border)",
    fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap",
  },
};
