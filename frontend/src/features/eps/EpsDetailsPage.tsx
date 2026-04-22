import { useEffect, useMemo, useState } from "react";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
} from "chart.js";
import { Bar } from "react-chartjs-2";

import { Skeleton } from "../../shared/ui/Skeleton";
import { getEpsBreakdown, getEpsDetails } from "./api";
import type {
  EpsBreakdownResponse, EpsClassRow, EpsDetailsResponse, EpsMonthlyRow,
} from "./types";

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend);

/**
 * EPS Details — 1:1 cu `renderEpsDetails` din app-ul vechi
 * (adeplast-dashboard/templates/index.html, linii 2746–2921).
 * Layout: section-title + subtitle → 3 cards-row (sales/qty/price) →
 * data table cu TOTAL → 2 chart-box (bar chart sales + qty), KA only.
 */

const MONTH_NAMES = [
  "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];

const currentYear = new Date().getFullYear();

function toNum(s: string | number): number {
  const n = typeof s === "number" ? s : parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}
function fmtNum(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}
function fmtDec(n: number, digits = 2): string {
  return new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}
function fmtPct(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}
function signNum(n: number): string {
  return `${n >= 0 ? "+" : ""}${fmtNum(n)}`;
}
function deltaColor(n: number): string {
  if (n > 0) return "var(--green)";
  if (n < 0) return "var(--red)";
  return "var(--muted)";
}

interface KaAggregated {
  byMonth: Array<{
    month: number;
    month_name: string;
    qty_y1: number;
    qty_y2: number;
    sales_y1: number;
    sales_y2: number;
  }>;
  totals: {
    qty_y1: number;
    qty_y2: number;
    sales_y1: number;
    sales_y2: number;
  };
}

function aggregateKa(rows: EpsMonthlyRow[]): KaAggregated {
  const ka = rows
    .filter((r) => r.category === "KA")
    .map((r) => ({
      month: r.month,
      month_name: r.monthName,
      qty_y1: toNum(r.qtyY1),
      qty_y2: toNum(r.qtyY2),
      sales_y1: toNum(r.salesY1),
      sales_y2: toNum(r.salesY2),
    }))
    .sort((a, b) => a.month - b.month);
  const totals = ka.reduce(
    (acc, r) => ({
      qty_y1: acc.qty_y1 + r.qty_y1,
      qty_y2: acc.qty_y2 + r.qty_y2,
      sales_y1: acc.sales_y1 + r.sales_y1,
      sales_y2: acc.sales_y2 + r.sales_y2,
    }),
    { qty_y1: 0, qty_y2: 0, sales_y1: 0, sales_y2: 0 },
  );
  return { byMonth: ka, totals };
}

export default function EpsDetailsPage() {
  const [y1, setY1] = useState<number>(currentYear - 1);
  const [y2, setY2] = useState<number>(currentYear);
  const [selectedMonths, setSelectedMonths] = useState<Set<number>>(new Set());
  const [data, setData] = useState<EpsDetailsResponse | null>(null);
  const [breakdown, setBreakdown] = useState<EpsBreakdownResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const q = {
      y1, y2,
      months: selectedMonths.size > 0
        ? [...selectedMonths].sort((a, b) => a - b)
        : undefined,
    };
    Promise.all([getEpsDetails(q), getEpsBreakdown(q)])
      .then(([det, bd]) => {
        if (cancelled) return;
        setData(det);
        setBreakdown(bd);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message || "Eroare la încărcarea datelor EPS");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [y1, y2, selectedMonths]);

  const agg = useMemo<KaAggregated | null>(
    () => (data ? aggregateKa(data.rows) : null),
    [data],
  );

  const hasData = agg && agg.byMonth.length > 0;

  const toggleMonth = (m: number) => {
    setSelectedMonths((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else next.add(m);
      return next;
    });
  };
  const clearMonths = () => setSelectedMonths(new Set());

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>
        EPS Detalii — Valoare și Cantitate
        {selectedMonths.size > 0 && (
          <span style={styles.monthFilterLabel}>
            {" · "}
            {[...selectedMonths].sort((a, b) => a - b).map((m) => MONTH_NAMES[m - 1]).join(", ")}
          </span>
        )}
      </div>
      <div style={styles.sectionSubtitle}>
        Comparație lunară {y1} vs {y2} — KA
      </div>

      <FilterBar
        y1={y1}
        y2={y2}
        onY1={setY1}
        onY2={setY2}
        selectedMonths={selectedMonths}
        onToggleMonth={toggleMonth}
        onClearMonths={clearMonths}
      />

      {loading && <SkeletonSection />}
      {!loading && error && (
        <div style={styles.errorBox}>Eroare: {error}</div>
      )}
      {!loading && !error && !hasData && (
        <div style={styles.emptyBox}>
          <div style={{ fontSize: 42 }}>📈</div>
          <p style={{ color: "var(--muted)" }}>
            Nu sunt date EPS pentru perioada selectată.
          </p>
        </div>
      )}

      {!loading && !error && hasData && agg && (
        <>
          <KpiCards
            y1={y1}
            y2={y2}
            salesY1={agg.totals.sales_y1}
            salesY2={agg.totals.sales_y2}
            qtyY1={agg.totals.qty_y1}
            qtyY2={agg.totals.qty_y2}
          />
          <DataTable y1={y1} y2={y2} agg={agg} />
          <ChartsRow y1={y1} y2={y2} byMonth={agg.byMonth} />
          {breakdown && breakdown.rows.length > 0 && (
            <ClassBreakdown y1={y1} y2={y2} rows={breakdown.rows} />
          )}
        </>
      )}
    </div>
  );
}

function FilterBar({
  y1,
  y2,
  onY1,
  onY2,
  selectedMonths,
  onToggleMonth,
  onClearMonths,
}: {
  y1: number;
  y2: number;
  onY1: (n: number) => void;
  onY2: (n: number) => void;
  selectedMonths: Set<number>;
  onToggleMonth: (m: number) => void;
  onClearMonths: () => void;
}) {
  const yearOptions = [currentYear - 3, currentYear - 2, currentYear - 1, currentYear];
  return (
    <div style={styles.filterBar}>
      <div style={styles.yearGroup}>
        <label style={styles.yearLabel}>An 1</label>
        <select
          value={y1}
          onChange={(e) => onY1(Number(e.target.value))}
          style={styles.select}
        >
          {yearOptions.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <span style={{ color: "var(--muted)" }}>vs</span>
        <label style={styles.yearLabel}>An 2</label>
        <select
          value={y2}
          onChange={(e) => onY2(Number(e.target.value))}
          style={styles.select}
        >
          {yearOptions.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>
      <div data-chipgrid="true" style={{
        display: "grid",
        gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
        gap: 5,
      }}>
        {selectedMonths.size > 0 ? (
          <button
            type="button"
            data-compact="true"
            onClick={onClearMonths}
            style={epsChip(false, "#ef4444")}
            title="Afișează toate lunile"
          >
            ✗ clear
          </button>
        ) : <span />}
        <span style={{ gridColumn: "span 6" }} />
        {MONTH_NAMES.map((name, i) => {
          const m = i + 1;
          const active = selectedMonths.has(m);
          return (
            <button
              key={m}
              type="button"
              data-compact="true"
              onClick={() => onToggleMonth(m)}
              style={epsChip(active, "#22c55e")}
              aria-pressed={active}
            >
              {name.slice(0, 3).toLowerCase()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function KpiCards({
  y1,
  y2,
  salesY1,
  salesY2,
  qtyY1,
  qtyY2,
}: {
  y1: number;
  y2: number;
  salesY1: number;
  salesY2: number;
  qtyY1: number;
  qtyY2: number;
}) {
  const diffSales = salesY2 - salesY1;
  const pctSales = salesY1 !== 0 ? (diffSales / salesY1) * 100 : 0;
  const diffQty = qtyY2 - qtyY1;
  const pctQty = qtyY1 !== 0 ? (diffQty / qtyY1) * 100 : 0;
  const priceY1 = qtyY1 !== 0 ? salesY1 / qtyY1 : 0;
  const priceY2 = qtyY2 !== 0 ? salesY2 / qtyY2 : 0;
  const diffPrice = priceY2 - priceY1;
  const pctPrice = priceY1 !== 0 ? (diffPrice / priceY1) * 100 : 0;
  return (
    <>
      <div style={styles.cardsRow}>
        <Card label={`Vânzări ${y1}`} value={fmtNum(salesY1)} sub="RON" />
        <Card label={`Vânzări ${y2}`} value={fmtNum(salesY2)} sub="RON" />
        <Card
          label="Dif. Valoare"
          value={signNum(diffSales)}
          sub={fmtPct(pctSales)}
          valueColor={deltaColor(diffSales)}
        />
      </div>
      <div style={styles.cardsRow}>
        <Card label={`Cantitate ${y1}`} value={fmtNum(qtyY1)} sub="mc" />
        <Card label={`Cantitate ${y2}`} value={fmtNum(qtyY2)} sub="mc" />
        <Card
          label="Dif. Cantitate"
          value={signNum(diffQty)}
          sub={fmtPct(pctQty)}
          valueColor={deltaColor(diffQty)}
        />
      </div>
      <div style={styles.cardsRow}>
        <Card label={`Preț mediu/mc ${y1}`} value={fmtDec(priceY1)} sub="RON/mc" />
        <Card label={`Preț mediu/mc ${y2}`} value={fmtDec(priceY2)} sub="RON/mc" />
        <Card
          label="Dif. Preț/mc"
          value={`${diffPrice >= 0 ? "+" : ""}${fmtDec(diffPrice)}`}
          sub={fmtPct(pctPrice)}
          valueColor={deltaColor(diffPrice)}
        />
      </div>
    </>
  );
}

function Card({
  label,
  value,
  sub,
  valueColor,
}: {
  label: string;
  value: string;
  sub: string;
  valueColor?: string;
}) {
  return (
    <div style={styles.card}>
      <div style={styles.cardLabel}>{label}</div>
      <div style={{ ...styles.cardValue, color: valueColor ?? "var(--text)" }}>
        {value}
      </div>
      <div style={styles.cardSub}>{sub}</div>
    </div>
  );
}

function DataTable({
  y1,
  y2,
  agg,
}: {
  y1: number;
  y2: number;
  agg: KaAggregated;
}) {
  const { byMonth, totals } = agg;
  const priceY1Total = totals.qty_y1 !== 0 ? totals.sales_y1 / totals.qty_y1 : 0;
  const priceY2Total = totals.qty_y2 !== 0 ? totals.sales_y2 / totals.qty_y2 : 0;
  return (
    <div style={styles.tableBox}>
      <h3 style={styles.tableTitle}>Date Complete EPS — KA (Valoare + Cantitate + Preț/mc)</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr style={styles.thRow}>
              <th style={styles.th}>Luna</th>
              <th style={styles.thRight}>Vânzări {y1}</th>
              <th style={styles.thRight}>Vânzări {y2}</th>
              <th style={styles.thRight}>Dif. Vz</th>
              <th style={styles.thRight}>%</th>
              <th style={styles.thRight}>Cant. {y1}</th>
              <th style={styles.thRight}>Cant. {y2}</th>
              <th style={styles.thRight}>Dif. Cant.</th>
              <th style={styles.thRight}>%</th>
              <th style={styles.thRight}>Preț/mc {String(y1).slice(-2)}</th>
              <th style={styles.thRight}>Preț/mc {String(y2).slice(-2)}</th>
            </tr>
          </thead>
          <tbody>
            {byMonth.map((r) => {
              const dv = r.sales_y2 - r.sales_y1;
              const pv = r.sales_y1 !== 0 ? (dv / r.sales_y1) * 100 : 0;
              const dq = r.qty_y2 - r.qty_y1;
              const pq = r.qty_y1 !== 0 ? (dq / r.qty_y1) * 100 : 0;
              const pm1 = r.qty_y1 !== 0 ? r.sales_y1 / r.qty_y1 : 0;
              const pm2 = r.qty_y2 !== 0 ? r.sales_y2 / r.qty_y2 : 0;
              return (
                <tr key={r.month} style={styles.tr}>
                  <td style={styles.td}>{r.month_name}</td>
                  <td style={styles.tdRight}>{fmtNum(r.sales_y1)}</td>
                  <td style={styles.tdRight}>{fmtNum(r.sales_y2)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(dv) }}>{signNum(dv)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(pv) }}>{fmtPct(pv)}</td>
                  <td style={styles.tdRight}>{fmtNum(r.qty_y1)}</td>
                  <td style={styles.tdRight}>{fmtNum(r.qty_y2)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(dq) }}>{signNum(dq)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(pq) }}>{fmtPct(pq)}</td>
                  <td style={styles.tdRight}>{fmtDec(pm1)}</td>
                  <td style={styles.tdRight}>{fmtDec(pm2)}</td>
                </tr>
              );
            })}
            <tr style={styles.totalRow}>
              <td style={styles.td}>TOTAL</td>
              <td style={styles.tdRight}>{fmtNum(totals.sales_y1)}</td>
              <td style={styles.tdRight}>{fmtNum(totals.sales_y2)}</td>
              <td style={{ ...styles.tdRight, color: deltaColor(totals.sales_y2 - totals.sales_y1) }}>
                {signNum(totals.sales_y2 - totals.sales_y1)}
              </td>
              <td style={styles.tdRight}>
                {fmtPct(
                  totals.sales_y1 !== 0
                    ? ((totals.sales_y2 - totals.sales_y1) / totals.sales_y1) * 100
                    : 0,
                )}
              </td>
              <td style={styles.tdRight}>{fmtNum(totals.qty_y1)}</td>
              <td style={styles.tdRight}>{fmtNum(totals.qty_y2)}</td>
              <td style={{ ...styles.tdRight, color: deltaColor(totals.qty_y2 - totals.qty_y1) }}>
                {signNum(totals.qty_y2 - totals.qty_y1)}
              </td>
              <td style={styles.tdRight}>
                {fmtPct(
                  totals.qty_y1 !== 0
                    ? ((totals.qty_y2 - totals.qty_y1) / totals.qty_y1) * 100
                    : 0,
                )}
              </td>
              <td style={styles.tdRight}>{fmtDec(priceY1Total)}</td>
              <td style={styles.tdRight}>{fmtDec(priceY2Total)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChartsRow({
  y1,
  y2,
  byMonth,
}: {
  y1: number;
  y2: number;
  byMonth: KaAggregated["byMonth"];
}) {
  const labels = byMonth.map((r) => r.month_name);
  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: { color: "#e0e0e0", font: { size: 11 } },
      },
      tooltip: {
        backgroundColor: "#111827",
        titleColor: "#e0e0e0",
        bodyColor: "#e0e0e0",
        borderColor: "#1e293b",
        borderWidth: 1,
      },
    },
    scales: {
      x: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "#1e293b" } },
      y: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "#1e293b" } },
    },
  } as const;
  return (
    <div style={styles.chartsGrid}>
      <div style={styles.chartBox}>
        <h3 style={styles.chartTitle}>Vânzări EPS Lunare (RON)</h3>
        <div style={styles.chartWrap}>
          <Bar
            data={{
              labels,
              datasets: [
                {
                  label: String(y1),
                  data: byMonth.map((r) => r.sales_y1),
                  backgroundColor: "rgba(251,146,60,0.7)",
                  borderColor: "rgba(251,146,60,1)",
                  borderWidth: 1,
                },
                {
                  label: String(y2),
                  data: byMonth.map((r) => r.sales_y2),
                  backgroundColor: "rgba(167,139,250,0.7)",
                  borderColor: "rgba(167,139,250,1)",
                  borderWidth: 1,
                },
              ],
            }}
            options={chartOpts}
          />
        </div>
      </div>
      <div style={styles.chartBox}>
        <h3 style={styles.chartTitle}>Cantități EPS Lunare (mc)</h3>
        <div style={styles.chartWrap}>
          <Bar
            data={{
              labels,
              datasets: [
                {
                  label: String(y1),
                  data: byMonth.map((r) => r.qty_y1),
                  backgroundColor: "rgba(34,211,238,0.7)",
                  borderColor: "rgba(34,211,238,1)",
                  borderWidth: 1,
                },
                {
                  label: String(y2),
                  data: byMonth.map((r) => r.qty_y2),
                  backgroundColor: "rgba(52,211,153,0.7)",
                  borderColor: "rgba(52,211,153,1)",
                  borderWidth: 1,
                },
              ],
            }}
            options={chartOpts}
          />
        </div>
      </div>
    </div>
  );
}

function ClassBreakdown({
  y1, y2, rows,
}: { y1: number; y2: number; rows: EpsClassRow[] }) {
  // Sortare numerică pe clasa (50, 70, 80, 100, 120, 150, 200).
  const sorted = [...rows].sort((a, b) => {
    const na = parseInt(a.cls, 10);
    const nb = parseInt(b.cls, 10);
    if (Number.isNaN(na) && Number.isNaN(nb)) return 0;
    if (Number.isNaN(na)) return 1;
    if (Number.isNaN(nb)) return -1;
    return na - nb;
  });

  // Totals
  const tot = sorted.reduce(
    (a, r) => ({
      s1: a.s1 + toNum(r.salesY1),
      s2: a.s2 + toNum(r.salesY2),
      q1: a.q1 + toNum(r.qtyY1),
      q2: a.q2 + toNum(r.qtyY2),
    }),
    { s1: 0, s2: 0, q1: 0, q2: 0 },
  );

  return (
    <div style={styles.tableBox}>
      <h3 style={styles.tableTitle}>
        Breakdown pe clase EPS (KA, plăci) — verificare sursă eroare
      </h3>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr style={styles.thRow}>
              <th style={styles.th}>Clasă</th>
              <th style={styles.thRight}>Vânzări {y1}</th>
              <th style={styles.thRight}>Vânzări {y2}</th>
              <th style={styles.thRight}>Dif. Vz</th>
              <th style={styles.thRight}>%</th>
              <th style={styles.thRight}>Cant. {y1}</th>
              <th style={styles.thRight}>Cant. {y2}</th>
              <th style={styles.thRight}>Dif. Cant.</th>
              <th style={styles.thRight}>%</th>
              <th style={styles.thRight}>Preț/u {String(y1).slice(-2)}</th>
              <th style={styles.thRight}>Preț/u {String(y2).slice(-2)}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const s1 = toNum(r.salesY1);
              const s2 = toNum(r.salesY2);
              const q1 = toNum(r.qtyY1);
              const q2 = toNum(r.qtyY2);
              const dv = s2 - s1;
              const pv = s1 !== 0 ? (dv / s1) * 100 : 0;
              const dq = q2 - q1;
              const pq = q1 !== 0 ? (dq / q1) * 100 : 0;
              const p1 = q1 !== 0 ? s1 / q1 : 0;
              const p2 = q2 !== 0 ? s2 / q2 : 0;
              return (
                <tr key={r.cls} style={styles.tr}>
                  <td style={styles.td}>EPS {r.cls}</td>
                  <td style={styles.tdRight}>{fmtNum(s1)}</td>
                  <td style={styles.tdRight}>{fmtNum(s2)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(dv) }}>{signNum(dv)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(pv) }}>{fmtPct(pv)}</td>
                  <td style={styles.tdRight}>{fmtNum(q1)}</td>
                  <td style={styles.tdRight}>{fmtNum(q2)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(dq) }}>{signNum(dq)}</td>
                  <td style={{ ...styles.tdRight, color: deltaColor(pq) }}>{fmtPct(pq)}</td>
                  <td style={styles.tdRight}>{fmtDec(p1)}</td>
                  <td style={styles.tdRight}>{fmtDec(p2)}</td>
                </tr>
              );
            })}
            <tr style={styles.totalRow}>
              <td style={styles.td}>TOTAL</td>
              <td style={styles.tdRight}>{fmtNum(tot.s1)}</td>
              <td style={styles.tdRight}>{fmtNum(tot.s2)}</td>
              <td style={{ ...styles.tdRight, color: deltaColor(tot.s2 - tot.s1) }}>
                {signNum(tot.s2 - tot.s1)}
              </td>
              <td style={styles.tdRight}>
                {fmtPct(tot.s1 !== 0 ? ((tot.s2 - tot.s1) / tot.s1) * 100 : 0)}
              </td>
              <td style={styles.tdRight}>{fmtNum(tot.q1)}</td>
              <td style={styles.tdRight}>{fmtNum(tot.q2)}</td>
              <td style={{ ...styles.tdRight, color: deltaColor(tot.q2 - tot.q1) }}>
                {signNum(tot.q2 - tot.q1)}
              </td>
              <td style={styles.tdRight}>
                {fmtPct(tot.q1 !== 0 ? ((tot.q2 - tot.q1) / tot.q1) * 100 : 0)}
              </td>
              <td style={styles.tdRight}>
                {fmtDec(tot.q1 !== 0 ? tot.s1 / tot.q1 : 0)}
              </td>
              <td style={styles.tdRight}>
                {fmtDec(tot.q2 !== 0 ? tot.s2 / tot.q2 : 0)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SkeletonSection() {
  return (
    <div>
      <div style={styles.cardsRow}>
        <Skeleton height={92} />
        <Skeleton height={92} />
        <Skeleton height={92} />
      </div>
      <Skeleton height={280} />
    </div>
  );
}

function epsChip(active: boolean, color: string): React.CSSProperties {
  return {
    padding: "4px 6px", fontSize: 11, fontWeight: 600,
    background: active ? color : "#fff",
    color: active ? "#fff" : color,
    border: `1px solid ${active ? color : color + "55"}`,
    borderRadius: 8, cursor: "pointer", whiteSpace: "nowrap",
    minHeight: 30, minWidth: 0,
  };
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    display: "flex", flexDirection: "column", gap: 12,
    padding: "4px 4px 20px", color: "var(--text)",
    zoom: 0.80 as unknown as number,
  },
  sectionTitle: { fontSize: 18, fontWeight: 600, color: "var(--text)" },
  monthFilterLabel: { fontSize: 14, fontWeight: 500, color: "var(--muted)" },
  sectionSubtitle: { fontSize: 13, color: "var(--muted)", marginTop: -8 },
  filterBar: {
    display: "flex",
    gap: 16,
    alignItems: "center",
    flexWrap: "wrap",
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "10px 14px",
  },
  yearGroup: { display: "flex", gap: 8, alignItems: "center" },
  yearLabel: { fontSize: 12, color: "var(--muted)" },
  select: {
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: "6px 10px",
    fontSize: 13,
  },
  monthChips: { display: "flex", gap: 3, flexWrap: "nowrap", alignItems: "center", overflowX: "auto" },
  monthChip: {
    padding: "4px 12px",
    fontSize: 12,
    borderRadius: 16,
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--muted)",
    cursor: "pointer",
  },
  monthChipActive: {
    background: "var(--cyan)",
    color: "#0a0e17",
    borderColor: "var(--cyan)",
  },
  clearBtn: {
    padding: "4px 10px",
    fontSize: 11,
    background: "transparent",
    border: "1px solid var(--warning)",
    color: "var(--warning)",
    borderRadius: 16,
    cursor: "pointer",
    marginLeft: 6,
  },
  cardsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 14,
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 10px",
    borderTop: "3px solid var(--cyan)",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minHeight: 58,
  },
  cardLabel: {
    fontSize: 10.5,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
    marginBottom: 2,
    lineHeight: 1.2,
  },
  cardValue: { fontSize: 18, fontWeight: 800, lineHeight: 1.15 },
  cardSub: { fontSize: 10.5, color: "var(--muted)", marginTop: 2, lineHeight: 1.2 },
  tableBox: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 18,
  },
  tableTitle: {
    fontSize: 14,
    fontWeight: 600,
    margin: "0 0 12px",
    color: "var(--text)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
  },
  thRow: { borderBottom: "1px solid var(--border)" },
  th: {
    textAlign: "left",
    padding: "8px 8px",
    fontSize: 11,
    textTransform: "uppercase",
    color: "var(--muted)",
    fontWeight: 600,
  },
  thRight: {
    textAlign: "right",
    padding: "8px 8px",
    fontSize: 11,
    textTransform: "uppercase",
    color: "var(--muted)",
    fontWeight: 600,
  },
  tr: { borderBottom: "1px solid rgba(30,41,59,0.5)" },
  td: { padding: "9px 8px", color: "var(--text)" },
  tdRight: { padding: "9px 8px", textAlign: "right", color: "var(--text)" },
  totalRow: {
    fontWeight: 700,
    borderTop: "2px solid var(--cyan)",
    background: "rgba(34,211,238,0.04)",
  },
  chartsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: 16,
  },
  chartBox: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 18,
  },
  chartTitle: {
    fontSize: 14,
    fontWeight: 600,
    margin: "0 0 12px",
    color: "var(--text)",
  },
  chartWrap: { height: 280 },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 16,
    borderRadius: 8,
  },
  emptyBox: {
    padding: "64px 24px",
    textAlign: "center",
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
  },
};
