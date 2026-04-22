import { useEffect, useMemo, useState } from "react";

import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";

import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { getPrognoza } from "./api";
import type { AgentRow, ForecastPoint, HistoryPoint, PrognozaResponse, PrognozaScope } from "./types";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

function scopeFromCompany(c: CompanyScope): PrognozaScope {
  return c === "adeplast" ? "adp" : (c as PrognozaScope);
}

function scopeLabel(s: PrognozaScope): string {
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

function fmtPctSigned(v: string | number | null | undefined): string | null {
  if (v == null || v === "") return null;
  const n = toNum(v);
  if (!Number.isFinite(n)) return null;
  const rounded = Math.round(n * 10) / 10;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded.toFixed(1)}%`;
}

function methodLabel(m: string): string {
  if (m === "moving_avg_3m_with_seasonal") return "Medie mobilă 3 luni × factor sezonal";
  if (m === "moving_avg_3m") return "Medie mobilă 3 luni";
  return m;
}

export default function PrognozaPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const [horizon, setHorizon] = useState<number>(3);
  const [data, setData] = useState<PrognozaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPrognoza({ scope: apiScope, horizonMonths: horizon })
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiScope, horizon]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} - Prognoză Vânzări
          {data?.lastCompleteMonth ? ` (ancoră: ${data.lastCompleteMonth})` : ""}
        </h1>
        <HorizonSelector value={horizon} onChange={setHorizon} />
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {data && (
        <>
          <ChartCard
            history={data.history}
            forecast={data.forecast}
            method={methodLabel(data.method)}
          />
          <AgentTableCard
            agents={data.agents}
            forecast={data.forecast}
          />
        </>
      )}
    </div>
  );
}

function HorizonSelector({
  value,
  onChange,
}: {
  value: number;
  onChange: (h: number) => void;
}) {
  const options = [1, 2, 3, 6, 12];
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      style={styles.horizonSelect}
    >
      {options.map((h) => (
        <option key={h} value={h}>
          {h} {h === 1 ? "lună" : "luni"}
        </option>
      ))}
    </select>
  );
}

function ChartCard({
  history,
  forecast,
  method,
}: {
  history: HistoryPoint[];
  forecast: ForecastPoint[];
  method: string;
}) {
  const totalForecast = useMemo(
    () => forecast.reduce((acc, p) => acc + toNum(p.forecastSales), 0),
    [forecast],
  );
  const totalHistory12m = useMemo(
    () => history.reduce((acc, p) => acc + toNum(p.sales), 0),
    [history],
  );

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <div>
          <h2 style={styles.cardTitle}>Istoric vs. Predicție</h2>
          <div style={styles.subtitle}>Metodă: {method}</div>
        </div>
        <div style={styles.summaryGroup}>
          <SummaryPill
            label="Istoric (12 luni)"
            value={fmtRo(totalHistory12m)}
            tone="neutral"
          />
          <SummaryPill
            label="Forecast total"
            value={fmtRo(totalForecast)}
            tone="accent"
          />
        </div>
      </div>
      <div style={styles.chartWrap}>
        <ForecastChart history={history} forecast={forecast} />
      </div>
    </div>
  );
}

function ForecastChart({
  history,
  forecast,
}: {
  history: HistoryPoint[];
  forecast: ForecastPoint[];
}) {
  // Extrage culorile rezolvate din CSS vars — chart.js nu interpretează var(...).
  const root = typeof window !== "undefined" ? document.documentElement : null;
  const cs = root ? getComputedStyle(root) : null;
  const tick = cs?.getPropertyValue("--muted").trim() || "#64748b";
  const text = cs?.getPropertyValue("--text").trim() || "#1f2937";
  const grid = cs?.getPropertyValue("--border").trim() || "#e5e7eb";

  const histLen = history.length;
  const fcLen = forecast.length;
  const labels = [
    ...history.map((h) => h.label),
    ...forecast.map((f) => f.label),
  ];

  // Istoric: valorile reale pe indexii 0..histLen-1, restul null (gap la join).
  const histData: (number | null)[] = [
    ...history.map((h) => toNum(h.sales)),
    ...forecast.map(() => null),
  ];
  // Forecast: null pe istoric, dar păstrăm ultimul punct istoric ca "ancoră"
  // ca linia dotted să continue fluent de la valoarea reală.
  const lastHistVal = histLen > 0 ? toNum(history[histLen - 1].sales) : null;
  const fcData: (number | null)[] = [
    ...history.map((_, i) => (i === histLen - 1 ? lastHistVal : null)),
    ...forecast.map((f) => toNum(f.forecastSales)),
  ];

  const histColor = "#2563eb";  // albastru — istoric real
  const fcColor = "#dc2626";    // roșu — predicție

  const data = {
    labels,
    datasets: [
      {
        label: "Istoric",
        data: histData,
        borderColor: histColor,
        backgroundColor: "rgba(37, 99, 235, 0.1)",
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: histColor,
        fill: false,
        tension: 0.25,
        spanGaps: false,
      },
      {
        label: "Predicție",
        data: fcData,
        borderColor: fcColor,
        backgroundColor: "rgba(220, 38, 38, 0.1)",
        borderWidth: 2,
        borderDash: [6, 4],
        pointRadius: 3,
        pointBackgroundColor: fcColor,
        fill: false,
        tension: 0.25,
        spanGaps: true,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index" as const, intersect: false },
    plugins: {
      legend: {
        position: "top" as const,
        labels: {
          color: text,
          boxWidth: 12,
          boxHeight: 12,
          font: { size: 12 },
        },
      },
      tooltip: {
        callbacks: {
          label: (ctx: { dataset: { label?: string }; parsed: { y: number | null } }) =>
            ctx.parsed.y == null
              ? ""
              : `${ctx.dataset.label}: ${fmtRo(ctx.parsed.y)} RON`,
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: tick,
          font: { size: 11 },
          // Separator vertical intre ultimul punct de istoric si primul forecast
          callback: function (this: unknown, _value: string | number, index: number) {
            const lbl = labels[index] ?? "";
            if (index === histLen - 1) return `${lbl} ←`;
            if (index === histLen) return `→ ${lbl}`;
            return lbl;
          },
        },
        grid: { color: grid },
      },
      y: {
        ticks: {
          color: tick,
          callback: (v: number | string) =>
            `${(Number(v) / 1_000_000).toFixed(1)}M`,
        },
        grid: { color: grid },
      },
    },
  };

  // Suppress unused var warning for fcLen — keeps API clean if needed later
  void fcLen;

  return <Line data={data} options={options} />;
}

function AgentTableCard({
  agents,
  forecast,
}: {
  agents: AgentRow[];
  forecast: ForecastPoint[];
}) {
  const grandHistory = agents.reduce((acc, a) => acc + toNum(a.historyTotal), 0);
  const grandForecast = agents.reduce((acc, a) => acc + toNum(a.forecastTotal), 0);
  const grandPerMonth = forecast.map((_f, idx) =>
    agents.reduce((acc, a) => acc + toNum(a.forecastMonths[idx]), 0),
  );

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>Defalcare per agent</h2>
        <div style={styles.subtitle}>
          Forecast pro-rata distribuit după cota agentului din ultimele 12 luni
        </div>
      </div>
      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>AGENT</th>
              <th style={styles.thNum}>ISTORIC 12L</th>
              {forecast.map((f) => (
                <th key={`${f.year}-${f.month}`} style={styles.thNum}>
                  {f.label}
                </th>
              ))}
              <th style={styles.thNum}>TOTAL FORECAST</th>
              <th style={{ ...styles.thNum, width: 70 }}>Δ%</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => {
              const hist = toNum(a.historyTotal);
              const fc = toNum(a.forecastTotal);
              // Normalizare: forecast pe horizon / luni istoric pe aceleasi luni
              const nMonths = forecast.length;
              const avgHistPerMonth = hist / 12;
              const avgFcPerMonth = nMonths > 0 ? fc / nMonths : 0;
              const pct =
                avgHistPerMonth > 0
                  ? ((avgFcPerMonth - avgHistPerMonth) / avgHistPerMonth) * 100
                  : null;
              return (
                <tr key={a.agentId ?? "unassigned"}>
                  <td style={styles.td}>{a.agentName}</td>
                  <td style={styles.tdNum}>{fmtRo(hist)}</td>
                  {a.forecastMonths.map((m, i) => (
                    <td key={i} style={styles.tdNum}>
                      {fmtRo(toNum(m))}
                    </td>
                  ))}
                  <td style={styles.tdNum}>{fmtRo(fc)}</td>
                  <td style={styles.tdNum}>
                    <PctBadge value={pct} />
                  </td>
                </tr>
              );
            })}
            <tr style={styles.totalRow}>
              <td style={styles.tdTotal}>TOTAL</td>
              <td style={styles.tdNumTotal}>{fmtRo(grandHistory)}</td>
              {grandPerMonth.map((v, i) => (
                <td key={i} style={styles.tdNumTotal}>
                  {fmtRo(v)}
                </td>
              ))}
              <td style={styles.tdNumTotal}>{fmtRo(grandForecast)}</td>
              <td style={styles.tdNumTotal}>—</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "neutral" | "accent";
}) {
  const fg = tone === "accent" ? "#dc2626" : "var(--muted)";
  const bg = tone === "accent" ? "rgba(220,38,38,0.08)" : "var(--accent-soft)";
  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        padding: "6px 12px",
        background: bg,
        borderRadius: 6,
        minWidth: 130,
      }}
    >
      <span style={{ fontSize: 10.5, color: "var(--muted)", letterSpacing: 0.4, textTransform: "uppercase" }}>
        {label}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, color: fg, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </span>
    </div>
  );
}

function PctBadge({ value }: { value: number | null }) {
  if (value == null || !Number.isFinite(value)) {
    return <span style={{ color: "var(--muted)" }}>—</span>;
  }
  const tone = value > 0 ? "pos" : value < 0 ? "neg" : "zero";
  const bg =
    tone === "pos"
      ? "rgba(5, 150, 105, 0.12)"
      : tone === "neg"
        ? "rgba(220, 38, 38, 0.12)"
        : "rgba(148, 163, 184, 0.12)";
  const fg =
    tone === "pos"
      ? "var(--green)"
      : tone === "neg"
        ? "var(--red)"
        : "var(--muted)";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 600,
        background: bg,
        color: fg,
        borderRadius: 999,
        whiteSpace: "nowrap",
      }}
    >
      {fmtPctSigned(value)}
    </span>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: "4px 4px 12px",
    color: "var(--text)",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 17,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: -0.2,
  },
  subtitle: {
    fontSize: 11.5,
    color: "var(--muted)",
    marginTop: 2,
  },
  horizonSelect: {
    padding: "7px 12px",
    fontSize: 13,
    background: "var(--bg-elevated)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    cursor: "pointer",
  },
  error: {
    color: "var(--red)",
    padding: 12,
    background: "rgba(220, 38, 38, 0.08)",
    borderRadius: 6,
  },
  loading: { color: "var(--muted)", padding: 12 },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
    gap: 12,
    flexWrap: "wrap",
  },
  cardTitle: {
    margin: 0,
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: 0.1,
  },
  summaryGroup: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  chartWrap: {
    width: "100%",
    height: 360,
  },
  tableWrap: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    textAlign: "left",
    padding: "6px 8px",
    fontSize: 10.5,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  thNum: {
    textAlign: "right",
    padding: "6px 8px",
    fontSize: 10.5,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  td: {
    padding: "7px 8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    whiteSpace: "nowrap",
  },
  tdNum: {
    padding: "7px 8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    whiteSpace: "nowrap",
  },
  totalRow: {
    background: "var(--accent-soft)",
  },
  tdTotal: {
    padding: "8px 8px",
    fontSize: 13,
    fontWeight: 700,
    color: "var(--text)",
    borderTop: "2px solid var(--border)",
    whiteSpace: "nowrap",
  },
  tdNumTotal: {
    padding: "8px 8px",
    fontSize: 13,
    fontWeight: 700,
    color: "var(--text)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    borderTop: "2px solid var(--border)",
    whiteSpace: "nowrap",
  },
};
