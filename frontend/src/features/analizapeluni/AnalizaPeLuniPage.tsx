import { useEffect, useMemo, useRef, useState } from "react";

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

import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { getAnalizaPeLuni } from "./api";
import type {
  AnalizaResponse,
  AnalizaScope,
  MonthTotalRow,
  YearTotals,
} from "./types";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

function scopeFromCompany(c: CompanyScope): AnalizaScope {
  return c === "adeplast" ? "adp" : (c as AnalizaScope);
}

function scopeLabel(s: AnalizaScope): string {
  if (s === "adp") return "Adeplast";
  if (s === "sika") return "Sika";
  return "SIKADP";
}

function sectionTitle(s: AnalizaScope): string {
  return s === "sikadp" ? "Total KA — SIKADP (combinat)" : "Total KA";
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

export default function AnalizaPeLuniPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [data, setData] = useState<AnalizaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAnalizaPeLuni({ scope: apiScope, year })
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
  }, [apiScope, year]);

  const visibleMonths = useMemo<MonthTotalRow[]>(() => {
    if (!data) return [];
    return data.monthTotals.filter(
      (m) => toNum(m.salesY1) > 0 || toNum(m.salesY2) > 0,
    );
  }, [data]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} - Vanzari Lunare Comparative{" "}
          {data?.yearPrev ?? year - 1} vs {data?.yearCurr ?? year}
        </h1>
        <YearSelector value={year} onChange={setYear} />
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {data && (
        <TotalKaCard
          title={sectionTitle(apiScope)}
          months={visibleMonths}
          grandTotals={data.grandTotals}
          yearPrev={data.yearPrev}
          yearCurr={data.yearCurr}
        />
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

function TotalKaCard({
  title,
  months,
  grandTotals,
  yearPrev,
  yearCurr,
}: {
  title: string;
  months: MonthTotalRow[];
  grandTotals: YearTotals;
  yearPrev: number;
  yearCurr: number;
}) {
  const [selected, setSelected] = useState<Set<number>>(() =>
    new Set(months.map((m) => m.month))
  );
  useEffect(() => {
    setSelected(new Set(months.map((m) => m.month)));
  }, [months]);

  const toggleMonth = (month: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(month)) next.delete(month);
      else next.add(month);
      return next;
    });
  };
  const allSelected = selected.size === months.length && months.length > 0;
  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(months.map((m) => m.month)));
  };

  const chartMonths = months.filter((m) => selected.has(m.month));

  // Recompute totals from selected months (grandTotals ramane doar dacă toate-s selectate).
  const selectedTotals = useMemo(() => {
    if (chartMonths.length === months.length) {
      return {
        salesY1: toNum(grandTotals.salesY1),
        salesY2: toNum(grandTotals.salesY2),
        diff: toNum(grandTotals.diff),
        pct: grandTotals.pct,
      };
    }
    const y1 = chartMonths.reduce((a, m) => a + toNum(m.salesY1), 0);
    const y2 = chartMonths.reduce((a, m) => a + toNum(m.salesY2), 0);
    const diff = y2 - y1;
    const pct = y1 > 0 ? (diff / y1) * 100 : null;
    return { salesY1: y1, salesY2: y2, diff, pct: pct?.toString() ?? null };
  }, [chartMonths, grandTotals, months.length]);

  const totalPctTone = pctTone(selectedTotals.pct);
  const totalPctFmt = fmtPctSigned(selectedTotals.pct) ?? "—";

  const tableRef = useRef<HTMLDivElement>(null);
  const [chartHeight, setChartHeight] = useState<number>(240);
  const [isMobile, setIsMobile] = useState<boolean>(() =>
    typeof window !== "undefined" &&
    window.matchMedia("(max-width: 768px)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const on = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  useEffect(() => {
    if (!tableRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const h = Math.round(e.contentRect.height);
        if (h > 0) setChartHeight(Math.max(h, 160));
      }
    });
    ro.observe(tableRef.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>{title}</h2>
        <PctBadge tone={totalPctTone} size="lg">
          {totalPctFmt}
        </PctBadge>
      </div>

      {/* Butoane selecție luni — grid 7 coloane × 2 rânduri (14 total) */}
      <div data-chipgrid="true" style={{
        display: "grid",
        gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
        gap: 6, marginBottom: 12,
      }}>
        <button
          type="button"
          data-compact="true"
          onClick={toggleAll}
          style={{
            padding: "4px 6px", fontSize: 11, fontWeight: 700,
            background: "#fff",
            color: allSelected ? "var(--red)" : "var(--accent)",
            border: `1px solid ${allSelected ? "var(--red)55" : "var(--accent)55"}`,
            borderRadius: 8, cursor: "pointer", whiteSpace: "nowrap",
            minHeight: 30, minWidth: 0,
          }}
        >
          {allSelected ? "✗ Nimic" : "✓ Toate"}
        </button>
        <span style={{ gridColumn: "span 6" }} />
        {months.map((m) => {
          const isSel = selected.has(m.month);
          return (
            <button
              key={m.month}
              type="button"
              data-compact="true"
              onClick={() => toggleMonth(m.month)}
              style={{
                padding: "4px 6px", fontSize: 11, fontWeight: 600,
                background: isSel ? "var(--accent)" : "#fff",
                color: isSel ? "#fff" : "var(--accent)",
                border: `1px solid ${isSel ? "var(--accent)" : "var(--accent)55"}`,
                borderRadius: 8, cursor: "pointer", whiteSpace: "nowrap",
                minHeight: 30, minWidth: 0,
              }}
            >
              {m.monthName.slice(0, 3)}
            </button>
          );
        })}
      </div>

      <div style={{
        ...styles.splitWrap,
        gridTemplateColumns: isMobile ? "minmax(0, 1fr)" : "auto minmax(0, 1fr)",
      }}>
        <div style={styles.tableCol} ref={tableRef}>
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
              {chartMonths.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    style={{ padding: 24, textAlign: "center", color: "var(--muted)", fontSize: 13 }}
                  >
                    Selectează cel puțin o lună
                  </td>
                </tr>
              ) : chartMonths.map((m) => (
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
              {chartMonths.length > 0 && (
                <tr style={styles.totalRow}>
                  <td style={styles.tdTotal}>TOTAL</td>
                  <td style={styles.tdNumTotal}>{fmtRo(selectedTotals.salesY1)}</td>
                  <td style={styles.tdNumTotal}>{fmtRo(selectedTotals.salesY2)}</td>
                  <td style={styles.tdNumTotal}>
                    <DiffPill value={selectedTotals.diff} />
                  </td>
                  <td style={styles.tdNumTotal}>
                    <PctBadge tone={totalPctTone} size="md">
                      {totalPctFmt}
                    </PctBadge>
                  </td>
                </tr>
              )}
            </tbody>
          </table>

        </div>
        <div style={{
          ...styles.chartCol,
          height: isMobile ? 280 : Math.max(chartHeight, 240),
          minHeight: 240,
          width: "100%",
        }}>
          <BarChart months={chartMonths} yearPrev={yearPrev} yearCurr={yearCurr} />
        </div>
      </div>
    </div>
  );
}

function BarChart({
  months,
  yearPrev,
  yearCurr,
}: {
  months: MonthTotalRow[];
  yearPrev: number;
  yearCurr: number;
}) {
  const labels = months.map((m) => m.monthName.slice(0, 3));
  const dataY1 = months.map((m) => toNum(m.salesY1));
  const dataY2 = months.map((m) => toNum(m.salesY2));

  // Extragem o dată culorile rezolvate din CSS vars la momentul render-ului —
  // chart.js nu interpretează `var(--...)` direct.
  const root = typeof window !== "undefined" ? document.documentElement : null;
  const cs = root ? getComputedStyle(root) : null;
  const tick = cs?.getPropertyValue("--muted").trim() || "#64748b";
  const text = cs?.getPropertyValue("--text").trim() || "#1f2937";
  const grid = (cs?.getPropertyValue("--border").trim() || "#e5e7eb");

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
