import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import {
  getBonusMagazinAnnual,
  getCompensation,
  getDashboard,
  getSalariuBonusAnnual,
} from "./api";
import { fmtRo, toNum } from "./shared";
import type {
  BonusMagazinAnnualResponse,
  DashboardAgentRow,
  DashboardResponse,
  SalariuBonusAnnualResponse,
} from "./types";

const MONTHS_SHORT = ["Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Noi", "Dec"];

/**
 * Dashboard agenți — KPI-uri agregate per agent: magazine, vânzări,
 * cheltuieli, % cost/vânzări, cost/100k vânzări, creștere YoY, bonus agent.
 * Selecție multiplă luni + An întreg + chart orizontal cu Cost% per agent.
 */
export default function DashboardAgentiPage() {
  const now = new Date();
  const [year, setYear] = useState<number>(now.getFullYear());
  // Set gol → An întreg (auto-limitat la lunile trecute pe backend).
  const [selectedMonths, setSelectedMonths] = useState<Set<number>>(() => new Set());
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [bonusData, setBonusData] = useState<BonusMagazinAnnualResponse | null>(null);
  const [salBonusData, setSalBonusData] = useState<SalariuBonusAnnualResponse | null>(null);
  const [ineligibleSet, setIneligibleSet] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const monthsArr = selectedMonths.size > 0 ? Array.from(selectedMonths).sort((a, b) => a - b) : null;
      const [d, b, sb, comp] = await Promise.all([
        getDashboard(year, monthsArr),
        getBonusMagazinAnnual(year),
        getSalariuBonusAnnual(year),
        getCompensation(),
      ]);
      setData(d);
      setBonusData(b);
      setSalBonusData(sb);
      setIneligibleSet(
        new Set(comp.rows.filter((r) => !r.bonusVanzariEligibil).map((r) => r.agentId)),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [year, selectedMonths]);

  useEffect(() => { void load(); }, [load]);

  const toggleMonth = (m: number) => {
    setSelectedMonths((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m); else next.add(m);
      return next;
    });
  };
  const selectAllMonths = () => setSelectedMonths(new Set());

  const years: number[] = [];
  for (let y = now.getFullYear() - 3; y <= now.getFullYear() + 1; y++) years.push(y);

  const isFullYear = selectedMonths.size === 0;
  const isCurrentYear = year === now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const periodLabel = isFullYear
    ? (isCurrentYear
        ? `YTD (Ian–${MONTHS_SHORT[currentMonth - 1]})`
        : year > now.getFullYear() ? "An (fără date)" : "An întreg")
    : Array.from(selectedMonths).sort((a, b) => a - b).map((m) => MONTHS_SHORT[m - 1]).join(", ");

  const rows = data?.rows ?? [];

  const chartRows = useMemo(() => {
    return rows
      .filter((r) => toNum(r.costPct) > 0)
      .map((r) => ({
        agentName: r.agentName,
        costPct: toNum(r.costPct),
        vanzari: toNum(r.vanzari),
      }))
      .sort((a, b) => b.costPct - a.costPct);
  }, [rows]);

  const maxPct = chartRows.length > 0 ? Math.max(...chartRows.map((r) => r.costPct)) : 0;

  return (
    <div className="agent-section" style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Dashboard Agenți</h1>
          <p style={styles.lead}>
            Performanță agregată per agent: vânzări, cheltuieli, eficiență și creștere.
          </p>
        </div>
        <div style={styles.controls}>
          <select
            data-wide="true"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={styles.selectYear}
          >
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      <div style={styles.periodPanel}>
        <div style={styles.periodHead}>
          <span style={styles.periodLabelTxt}>Perioadă</span>
          <label style={styles.fullYearToggle}>
            <input
              type="checkbox"
              checked={isFullYear}
              onChange={selectAllMonths}
              style={styles.checkbox}
            />
            <span style={isFullYear ? styles.fullYearActive : styles.fullYearIdle}>
              {isCurrentYear ? "YTD" : "An întreg"}
            </span>
          </label>
          <span style={styles.periodSep}>sau alege luni (bifează mai multe):</span>
          <span style={styles.periodCurrent}>
            → <strong style={styles.periodCurrentVal}>{periodLabel}</strong>
          </span>
          {!isFullYear && (
            <button onClick={selectAllMonths} style={styles.clearBtn}>Șterge</button>
          )}
        </div>
        <div style={styles.monthsCheckboxGrid}>
          {MONTHS_SHORT.map((name, idx) => {
            const m = idx + 1;
            const checked = selectedMonths.has(m);
            return (
              <label
                key={m}
                style={{ ...styles.monthCheck, ...(checked ? styles.monthCheckActive : {}) }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleMonth(m)}
                  style={styles.checkbox}
                />
                <span>{name}</span>
              </label>
            );
          })}
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : rows.length === 0 ? (
        <div style={styles.muted}>Nu există date.</div>
      ) : (
        <>
          <KpiStrip data={data!} />

          <div style={styles.tableWrap}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.thLeft}>Agent</th>
                  <th style={styles.th}>Nr. magazine</th>
                  <th style={styles.th}>Vânzări (RON)</th>
                  <th style={styles.th}>Cheltuieli (RON)</th>
                  <th style={styles.th}>% chelt./vânz.</th>
                  <th style={styles.th}>Cost / 100k vânz.</th>
                  <th style={styles.th}>YoY vânzări</th>
                  <th style={styles.th}>Bonus agent</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <Row
                    key={r.agentId}
                    r={r}
                    ineligible={ineligibleSet.has(r.agentId)}
                  />
                ))}
                {data && (
                  <tr>
                    <td style={styles.tdTotal}>TOTAL</td>
                    <td style={styles.tdTotalNum}>{data.grandStoreCount}</td>
                    <td style={styles.tdTotalNum}>{fmtRo(toNum(data.grandVanzari), 0)}</td>
                    <td style={styles.tdTotalNum}>{fmtRo(toNum(data.grandCheltuieli), 0)}</td>
                    <td style={styles.tdTotalNum}>
                      {data.grandCostPct != null ? `${fmtRo(toNum(data.grandCostPct), 2)}%` : "—"}
                    </td>
                    <td style={styles.tdTotal}></td>
                    <td style={styles.tdTotal}></td>
                    <td style={styles.tdTotalNum}>{fmtRo(toNum(data.grandBonusAgent), 0)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {chartRows.length > 0 && (
            <div style={styles.chartBox}>
              <div style={styles.chartTitle}>% cheltuieli / vânzări per agent</div>
              <div style={styles.chartBody}>
                {chartRows.map((c) => {
                  const widthPct = maxPct > 0 ? (c.costPct / maxPct) * 100 : 0;
                  return (
                    <div key={c.agentName} style={styles.barRow}>
                      <div style={styles.barLabel}>{c.agentName}</div>
                      <div style={styles.barTrack}>
                        <div style={{ ...styles.barFill, width: `${widthPct}%` }} />
                        <span style={styles.barValue}>{fmtRo(c.costPct, 2)}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {salBonusData && <SalariuBonusSection data={salBonusData} />}

          {bonusData && <BonusMagazinSection data={bonusData} />}
        </>
      )}
    </div>
  );
}

function SalariuBonusSection({ data }: { data: SalariuBonusAnnualResponse }) {
  const chartRows = data.rows
    .map((r) => ({ agentName: r.agentName, total: toNum(r.total) }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total);
  const maxTotal = chartRows.length > 0 ? Math.max(...chartRows.map((r) => r.total)) : 0;

  // Numărul de luni elapsed (luate în considerare pentru media lunară)
  const now = new Date();
  const monthsElapsed = data.year < now.getFullYear()
    ? 12
    : data.year > now.getFullYear()
      ? 0
      : now.getMonth() + 1;
  const avgDivisor = monthsElapsed > 0 ? monthsElapsed : 1;
  const grandAvg = monthsElapsed > 0 ? toNum(data.grandTotal) / avgDivisor : 0;

  return (
    <>
      <div style={{ ...styles.chartBox, marginTop: 12 }}>
        <div style={styles.chartTitle}>
          Salariu fix + Bonus agent per agent — {data.year} (matrice lunară)
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={styles.matrixTable}>
            <thead>
              <tr>
                <th style={styles.thLeft}>Agent</th>
                {MONTHS_SHORT.map((m, i) => (
                  <th key={i} style={styles.thMonth}>{m}</th>
                ))}
                <th style={styles.thMonth}>Total</th>
                <th style={styles.thMonth} title={`Total ÷ ${monthsElapsed} luni elapsed`}>
                  Media/lună
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => {
                const total = toNum(r.total);
                const media = monthsElapsed > 0 ? total / avgDivisor : 0;
                return (
                  <tr key={r.agentId}>
                    <td style={styles.tdLeft}>{r.agentName}</td>
                    {r.monthly.map((v, i) => {
                      const n = toNum(v);
                      return (
                        <td key={i} style={{ ...styles.tdMonth, color: n === 0 ? "var(--muted)" : undefined }}>
                          {n === 0 ? "—" : fmtRo(n, 0)}
                        </td>
                      );
                    })}
                    <td style={styles.tdTotalCell}>{fmtRo(total, 0)}</td>
                    <td style={styles.tdAvgCell}>
                      {monthsElapsed > 0 ? fmtRo(media, 0) : "—"}
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td style={styles.tdTotal}>TOTAL</td>
                {data.monthTotals.map((v, i) => (
                  <td key={i} style={styles.tdTotalNum}>{fmtRo(toNum(v), 0)}</td>
                ))}
                <td style={styles.tdTotalNum}>{fmtRo(toNum(data.grandTotal), 0)}</td>
                <td style={styles.tdTotalAvg}>
                  {monthsElapsed > 0 ? fmtRo(grandAvg, 0) : "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style={styles.avgNote}>
          Media/lună = Total ÷ {monthsElapsed} luni{" "}
          {data.year === now.getFullYear() ? "(elapsed până în luna curentă)" : data.year < now.getFullYear() ? "(anul complet)" : "(anul nu a început)"}
        </div>
      </div>

      {chartRows.length > 0 && (
        <div style={{ ...styles.chartBox, marginTop: 12 }}>
          <div style={styles.chartTitle}>
            Total salariu + bonus per agent — {data.year}
          </div>
          <div style={styles.chartBody}>
            {chartRows.map((c) => {
              const widthPct = maxTotal > 0 ? (c.total / maxTotal) * 100 : 0;
              return (
                <div key={c.agentName} style={styles.barRow}>
                  <div style={styles.barLabel}>{c.agentName}</div>
                  <div style={styles.barTrack}>
                    <div style={{ ...styles.barFillGreen, width: `${widthPct}%` }} />
                    <span style={styles.barValue}>{fmtRo(c.total, 0)} RON</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

function BonusMagazinSection({ data }: { data: BonusMagazinAnnualResponse }) {
  const chartRows = data.rows
    .map((r) => ({ agentName: r.agentName, total: toNum(r.total) }))
    .filter((r) => r.total > 0)
    .sort((a, b) => b.total - a.total);
  const maxTotal = chartRows.length > 0 ? Math.max(...chartRows.map((r) => r.total)) : 0;

  const now = new Date();
  const monthsElapsed = data.year < now.getFullYear()
    ? 12
    : data.year > now.getFullYear()
      ? 0
      : now.getMonth() + 1;
  const avgDivisor = monthsElapsed > 0 ? monthsElapsed : 1;
  const grandAvg = monthsElapsed > 0 ? toNum(data.grandTotal) / avgDivisor : 0;

  return (
    <>
      <div style={{ ...styles.chartBox, marginTop: 12 }}>
        <div style={styles.chartTitle}>
          Bonusuri magazine per agent — {data.year} (matrice lunară)
        </div>
        <div style={{ overflowX: "auto" }}>
          <table style={styles.matrixTable}>
            <thead>
              <tr>
                <th style={styles.thLeft}>Agent</th>
                {MONTHS_SHORT.map((m, i) => (
                  <th key={i} style={styles.thMonth}>{m}</th>
                ))}
                <th style={styles.thMonth}>Total</th>
                <th style={styles.thMonth} title={`Total ÷ ${monthsElapsed} luni elapsed`}>
                  Media/lună
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => {
                const total = toNum(r.total);
                const media = monthsElapsed > 0 ? total / avgDivisor : 0;
                return (
                  <tr key={r.agentId}>
                    <td style={styles.tdLeft}>{r.agentName}</td>
                    {r.monthly.map((v, i) => {
                      const n = toNum(v);
                      return (
                        <td key={i} style={{ ...styles.tdMonth, color: n === 0 ? "var(--muted)" : undefined }}>
                          {n === 0 ? "—" : fmtRo(n, 0)}
                        </td>
                      );
                    })}
                    <td style={styles.tdTotalCell}>{fmtRo(total, 0)}</td>
                    <td style={styles.tdAvgCell}>
                      {monthsElapsed > 0 ? fmtRo(media, 0) : "—"}
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td style={styles.tdTotal}>TOTAL</td>
                {data.monthTotals.map((v, i) => (
                  <td key={i} style={styles.tdTotalNum}>{fmtRo(toNum(v), 0)}</td>
                ))}
                <td style={styles.tdTotalNum}>{fmtRo(toNum(data.grandTotal), 0)}</td>
                <td style={styles.tdTotalAvg}>
                  {monthsElapsed > 0 ? fmtRo(grandAvg, 0) : "—"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style={styles.avgNote}>
          Media/lună = Total ÷ {monthsElapsed} luni{" "}
          {data.year === now.getFullYear() ? "(elapsed până în luna curentă)" : data.year < now.getFullYear() ? "(anul complet)" : "(anul nu a început)"}
        </div>
      </div>

      {chartRows.length > 0 && (
        <div style={{ ...styles.chartBox, marginTop: 12 }}>
          <div style={styles.chartTitle}>
            Total bonusuri magazine per agent — {data.year}
          </div>
          <div style={styles.chartBody}>
            {chartRows.map((c) => {
              const widthPct = maxTotal > 0 ? (c.total / maxTotal) * 100 : 0;
              return (
                <div key={c.agentName} style={styles.barRow}>
                  <div style={styles.barLabel}>{c.agentName}</div>
                  <div style={styles.barTrack}>
                    <div style={{ ...styles.barFillBlue, width: `${widthPct}%` }} />
                    <span style={styles.barValue}>{fmtRo(c.total, 0)} RON</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

function Row({ r, ineligible = false }: { r: DashboardAgentRow; ineligible?: boolean }) {
  const costPct = toNum(r.costPct);
  const yoy = r.yoyPct != null ? toNum(r.yoyPct) : null;
  const pctColor = costPct === 0 ? "var(--muted)"
    : costPct < 50 ? "#86efac"
    : costPct < 80 ? "#fbbf24"
    : "#fca5a5";
  const yoyColor = yoy == null ? "var(--muted)"
    : yoy >= 0 ? "#86efac" : "#fca5a5";
  return (
    <tr>
      <td style={styles.tdLeft}>
        {r.agentName}
        {ineligible && (
          <span style={styles.noBonusBadge} title="Agent fără bonus de vânzări">
            fără bonus
          </span>
        )}
      </td>
      <td style={styles.td}>{r.storeCount}</td>
      <td style={styles.td}>{fmtRo(toNum(r.vanzari), 0)}</td>
      <td style={styles.td}>{fmtRo(toNum(r.cheltuieli), 0)}</td>
      <td style={{ ...styles.td, color: pctColor, fontWeight: 600 }}>
        {r.costPct != null ? `${fmtRo(costPct, 2)}%` : "—"}
      </td>
      <td style={styles.td}>
        {r.costPer100k != null ? fmtRo(toNum(r.costPer100k), 0) : "—"}
      </td>
      <td style={{ ...styles.td, color: yoyColor, fontWeight: 600 }}>
        {yoy != null ? `${yoy >= 0 ? "+" : ""}${fmtRo(yoy, 2)}%` : "—"}
      </td>
      <td style={styles.td}>{fmtRo(toNum(r.bonusAgent), 0)}</td>
    </tr>
  );
}

function KpiStrip({ data }: { data: DashboardResponse }) {
  const v = toNum(data.grandVanzari);
  const c = toNum(data.grandCheltuieli);
  const pct = data.grandCostPct != null ? toNum(data.grandCostPct) : null;
  return (
    <div style={styles.kpiStrip}>
      <Kpi label="Agenți" value={String(data.rows.length)} />
      <Kpi label="Magazine" value={String(data.grandStoreCount)} />
      <Kpi label="Vânzări totale" value={`${fmtRo(v, 0)} RON`} />
      <Kpi label="Cheltuieli totale" value={`${fmtRo(c, 0)} RON`} />
      <Kpi label="% chelt./vânz." value={pct != null ? `${fmtRo(pct, 2)}%` : "—"} />
      <Kpi label="Bonus agenți" value={`${fmtRo(toNum(data.grandBonusAgent), 0)} RON`} />
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.kpi}>
      <span style={styles.kpiLabel}>{label}</span>
      <span style={styles.kpiValue}>{value}</span>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "12px 8px", width: "100%" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 10, flexWrap: "wrap" },
  title: { fontSize: 18, fontWeight: 700, color: "var(--cyan)", margin: "0 0 2px" },
  lead: { color: "var(--muted)", fontSize: 11, margin: 0, maxWidth: 640, lineHeight: 1.4 },
  controls: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  periodPanel: {
    padding: "8px 12px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    marginBottom: 10,
  },
  periodHead: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 8 },
  periodLabelTxt: { fontSize: 10, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" },
  fullYearToggle: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    cursor: "pointer",
    padding: "3px 8px",
    border: "1px solid var(--border)",
    borderRadius: 4,
  },
  fullYearIdle: { fontSize: 12, fontWeight: 600, color: "var(--muted)" },
  fullYearActive: { fontSize: 12, fontWeight: 700, color: "var(--cyan)" },
  periodSep: { fontSize: 11, color: "var(--muted)" },
  periodCurrent: { fontSize: 11, color: "var(--muted)" },
  periodCurrentVal: { color: "var(--cyan)", fontSize: 12 },
  monthsCheckboxGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(82px, 1fr))",
    gap: 4,
  },
  monthCheck: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 8px",
    fontSize: 11,
    fontWeight: 600,
    color: "var(--muted)",
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    cursor: "pointer",
    userSelect: "none",
  },
  monthCheckActive: { background: "rgba(6,182,212,0.15)", color: "var(--cyan)", borderColor: "var(--cyan)" },
  checkbox: { cursor: "pointer", accentColor: "var(--cyan)" },
  clearBtn: {
    marginLeft: "auto",
    padding: "3px 10px",
    fontSize: 11,
    fontWeight: 600,
    background: "transparent",
    color: "var(--muted)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    cursor: "pointer",
  },
  selectYear: {
    minWidth: 90,
    padding: "5px 8px",
    fontSize: 13,
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 4,
  },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "6px 10px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "6px 0" },
  kpiStrip: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 8,
    marginBottom: 12,
  },
  kpi: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    padding: "10px 12px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 6,
  },
  kpiLabel: { fontSize: 10, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" },
  kpiValue: { fontSize: 14, fontWeight: 700, color: "var(--cyan)", fontVariantNumeric: "tabular-nums" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", marginBottom: 12 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: { padding: "8px 6px", textAlign: "right", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  thLeft: { padding: "8px 10px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  td: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { padding: "6px 10px", textAlign: "left", borderBottom: "1px solid var(--border)" },
  noBonusBadge: {
    display: "inline-block",
    marginLeft: 8,
    padding: "1px 6px",
    fontSize: 9,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    background: "rgba(239,68,68,0.15)",
    color: "#fca5a5",
    border: "1px solid rgba(239,68,68,0.4)",
    borderRadius: 3,
    verticalAlign: "middle",
  },
  tdTotal: { padding: "10px 10px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "2px solid var(--border)" },
  tdTotalNum: { padding: "10px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
  chartBox: {
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "12px 14px",
  },
  chartTitle: { fontSize: 12, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 },
  chartBody: { display: "flex", flexDirection: "column", gap: 6 },
  barRow: { display: "grid", gridTemplateColumns: "180px 1fr", alignItems: "center", gap: 10 },
  barLabel: { fontSize: 12, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  barTrack: {
    position: "relative",
    height: 20,
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: 4,
    overflow: "hidden",
  },
  barFill: {
    position: "absolute",
    top: 0, left: 0, bottom: 0,
    background: "linear-gradient(90deg, rgba(34,197,94,0.7), rgba(234,179,8,0.75), rgba(239,68,68,0.8))",
  },
  barFillBlue: {
    position: "absolute",
    top: 0, left: 0, bottom: 0,
    background: "linear-gradient(90deg, rgba(6,182,212,0.55), rgba(6,182,212,0.85))",
  },
  barFillGreen: {
    position: "absolute",
    top: 0, left: 0, bottom: 0,
    background: "linear-gradient(90deg, rgba(34,197,94,0.55), rgba(34,197,94,0.85))",
  },
  matrixTable: { width: "100%", borderCollapse: "collapse", fontSize: 11 },
  thMonth: { padding: "6px 4px", textAlign: "right", fontSize: 10, fontWeight: 600, color: "var(--muted)", borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", whiteSpace: "nowrap" },
  tdMonth: { padding: "4px 4px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" },
  tdTotalCell: { padding: "4px 6px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", fontWeight: 700, color: "var(--cyan)", whiteSpace: "nowrap" },
  tdAvgCell: { padding: "4px 6px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "#fbbf24", whiteSpace: "nowrap", background: "rgba(234,179,8,0.06)" },
  tdTotalAvg: { padding: "10px 8px", background: "rgba(234,179,8,0.12)", fontWeight: 700, color: "#fbbf24", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
  avgNote: { fontSize: 10, color: "var(--muted)", marginTop: 6, fontStyle: "italic" },
  barValue: {
    position: "absolute",
    right: 8,
    top: "50%",
    transform: "translateY(-50%)",
    fontSize: 11,
    fontWeight: 700,
    color: "var(--text)",
    fontVariantNumeric: "tabular-nums",
    textShadow: "0 0 3px var(--bg)",
  },
};
