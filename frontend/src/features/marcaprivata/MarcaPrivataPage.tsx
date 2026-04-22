import { useEffect, useMemo, useState } from "react";

import {
  BarElement,
  CategoryScale,
  type ChartOptions,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Title,
  Tooltip,
  type TooltipItem,
} from "chart.js";
import { Bar } from "react-chartjs-2";

import { ApiError } from "../../shared/api";
import { getMarcaPrivata } from "./api";
import type {
  MarcaPrivataResponse,
  MPClientRow,
  MPMonthCell,
  MPYearTotals,
} from "./types";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

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

function fmtPctSigned(v: string | number | null | undefined): string | null {
  if (v == null || v === "") return null;
  const n = toNum(v);
  if (!Number.isFinite(n)) return null;
  const rounded = Math.round(n * 10) / 10;
  const sign = rounded > 0 ? "+" : "";
  return `${sign}${rounded.toFixed(1)}%`;
}

type Tone = "pos" | "neg" | "zero";

function pctTone(v: string | number | null | undefined): Tone {
  if (v == null || v === "") return "zero";
  const n = toNum(v);
  if (n > 0) return "pos";
  if (n < 0) return "neg";
  return "zero";
}

export default function MarcaPrivataPage() {
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [data, setData] = useState<MarcaPrivataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMarcaPrivata({ scope: "adp", year })
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
  }, [year]);

  const visibleMonths = useMemo<MPMonthCell[]>(() => {
    if (!data) return [];
    return data.months.filter(
      (m) => toNum(m.salesY1) > 0 || toNum(m.salesY2) > 0,
    );
  }, [data]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          Adeplast - Marca Privata (KA){" "}
          {data?.yearPrev ?? year - 1} vs {data?.yearCurr ?? year}
        </h1>
        <YearSelector value={year} onChange={setYear} />
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {data && (
        <>
          <MonthlyCard
            months={visibleMonths}
            grandTotals={data.grandTotals}
            yearPrev={data.yearPrev}
            yearCurr={data.yearCurr}
          />

          {data.clients.length > 0 && (
            <ClientsCard
              clients={data.clients}
              yearPrev={data.yearPrev}
              yearCurr={data.yearCurr}
            />
          )}
        </>
      )}
    </div>
  );
}

function YearSelector({
  value,
  onChange,
}: {
  value: number;
  onChange: (y: number) => void;
}) {
  const current = new Date().getFullYear();
  const options = [current, current - 1, current - 2, current - 3];
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      style={styles.yearSelect}
    >
      {options.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </select>
  );
}

function MonthlyCard({
  months,
  grandTotals,
  yearPrev,
  yearCurr,
}: {
  months: MPMonthCell[];
  grandTotals: MPYearTotals;
  yearPrev: number;
  yearCurr: number;
}) {
  const totalPctTone = pctTone(grandTotals.pct);
  const totalPctFmt = fmtPctSigned(grandTotals.pct) ?? "—";

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>Total Marca Privată — KA</h2>
        <PctBadge tone={totalPctTone} size="lg">
          {totalPctFmt}
        </PctBadge>
      </div>

      <div style={styles.splitWrap}>
        <div style={styles.tableCol}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>LUNA</th>
                <th style={styles.thNum}>{yearPrev}</th>
                <th style={styles.thNum}>{yearCurr}</th>
                <th style={styles.thNum}>DIFERENTA</th>
                <th style={{ ...styles.thNum, width: 70 }}>%</th>
              </tr>
            </thead>
            <tbody>
              {months.map((m) => (
                <tr key={m.month}>
                  <td style={styles.td}>{m.monthName}</td>
                  <td style={styles.tdNum}>{fmtRo(toNum(m.salesY1))}</td>
                  <td style={styles.tdNum}>{fmtRo(toNum(m.salesY2))}</td>
                  <td style={styles.tdNum}>
                    <DiffPill value={toNum(m.diff)} />
                  </td>
                  <td style={styles.tdNum}>
                    <PctBadge tone={pctTone(m.pct)} size="md">
                      {fmtPctSigned(m.pct) ?? "—"}
                    </PctBadge>
                  </td>
                </tr>
              ))}
              <tr style={styles.totalRow}>
                <td style={styles.tdTotal}>TOTAL</td>
                <td style={styles.tdNumTotal}>{fmtRo(toNum(grandTotals.salesY1))}</td>
                <td style={styles.tdNumTotal}>{fmtRo(toNum(grandTotals.salesY2))}</td>
                <td style={styles.tdNumTotal}>
                  <DiffPill value={toNum(grandTotals.diff)} />
                </td>
                <td style={styles.tdNumTotal}>
                  <PctBadge tone={totalPctTone} size="md">
                    {totalPctFmt}
                  </PctBadge>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style={styles.chartCol}>
          <BarChart months={months} yearPrev={yearPrev} yearCurr={yearCurr} />
        </div>
      </div>
    </div>
  );
}

function ClientsCard({
  clients,
  yearPrev,
  yearCurr,
}: {
  clients: MPClientRow[];
  yearPrev: number;
  yearCurr: number;
}) {
  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>Clienti Marca Privată</h2>
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>CLIENT</th>
            <th style={styles.thNum}>{yearPrev}</th>
            <th style={styles.thNum}>{yearCurr}</th>
            <th style={styles.thNum}>DIFERENTA</th>
            <th style={{ ...styles.thNum, width: 70 }}>%</th>
          </tr>
        </thead>
        <tbody>
          {clients.map((c) => (
            <tr key={c.client}>
              <td style={styles.td}>{c.client}</td>
              <td style={styles.tdNum}>{fmtRo(toNum(c.salesY1))}</td>
              <td style={styles.tdNum}>{fmtRo(toNum(c.salesY2))}</td>
              <td style={styles.tdNum}>
                <DiffPill value={toNum(c.diff)} />
              </td>
              <td style={styles.tdNum}>
                <PctBadge tone={pctTone(c.pct)} size="md">
                  {fmtPctSigned(c.pct) ?? "—"}
                </PctBadge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BarChart({
  months,
  yearPrev,
  yearCurr,
}: {
  months: MPMonthCell[];
  yearPrev: number;
  yearCurr: number;
}) {
  const labels = months.map((m) => m.monthName.slice(0, 3));
  const dataY1 = months.map((m) => toNum(m.salesY1));
  const dataY2 = months.map((m) => toNum(m.salesY2));

  const root = typeof window !== "undefined" ? document.documentElement : null;
  const cs = root ? getComputedStyle(root) : null;
  const tick = cs?.getPropertyValue("--muted").trim() || "#64748b";
  const text = cs?.getPropertyValue("--text").trim() || "#1f2937";
  const grid = cs?.getPropertyValue("--border").trim() || "#e5e7eb";

  const data = {
    labels,
    datasets: [
      {
        label: String(yearPrev),
        data: dataY1,
        backgroundColor: "#3b82f6",
        borderRadius: 3,
        barThickness: 10,
      },
      {
        label: String(yearCurr),
        data: dataY2,
        backgroundColor: "#10b981",
        borderRadius: 3,
        barThickness: 10,
      },
    ],
  };

  const options: ChartOptions<"bar"> = {
    indexAxis: "y" as const,
    responsive: true,
    maintainAspectRatio: false,
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
          label: (ctx: TooltipItem<"bar">) =>
            `${ctx.dataset.label}: ${fmtRo(ctx.parsed.x ?? 0)}`,
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: tick,
          callback: (v: number | string) =>
            `${(Number(v) / 1_000_000).toFixed(1)}M`,
        },
        grid: { color: grid },
      },
      y: {
        ticks: { color: text, font: { size: 12 } },
        grid: { display: false },
      },
    },
  };

  return <Bar data={data} options={options} />;
}

function PctBadge({
  tone,
  size,
  children,
}: {
  tone: Tone;
  size: "md" | "lg";
  children: React.ReactNode;
}) {
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
        padding: size === "lg" ? "4px 12px" : "2px 8px",
        fontSize: size === "lg" ? 13 : 12,
        fontWeight: 600,
        background: bg,
        color: fg,
        borderRadius: 999,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

function DiffPill({ value }: { value: number }) {
  const tone: Tone = value > 0 ? "pos" : value < 0 ? "neg" : "zero";
  const bg =
    tone === "pos"
      ? "rgba(5, 150, 105, 0.12)"
      : tone === "neg"
        ? "rgba(220, 38, 38, 0.12)"
        : "rgba(148, 163, 184, 0.10)";
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
        padding: "3px 10px",
        fontSize: 13,
        fontWeight: 600,
        background: bg,
        color: fg,
        borderRadius: 6,
        fontVariantNumeric: "tabular-nums",
        whiteSpace: "nowrap",
      }}
    >
      {fmtSigned(value)}
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
  yearSelect: {
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
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    margin: 0,
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: 0.1,
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
  splitWrap: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    gap: 20,
    alignItems: "stretch",
  },
  tableCol: {
    minWidth: 0,
  },
  chartCol: {
    minWidth: 0,
    height: "100%",
    minHeight: 240,
  },
};
