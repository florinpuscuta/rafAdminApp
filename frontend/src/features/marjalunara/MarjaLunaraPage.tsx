import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getMarjaLunara } from "./api";
import type { MarjaLunaraResponse, MLMonthRow, MLScope } from "./types";


const MONTH_NAMES = [
  "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];


function scopeFromCompany(c: CompanyScope): MLScope {
  if (c === "sika") return "sika";
  if (c === "sikadp") return "sikadp";
  return "adp";
}

function scopeLabel(s: MLScope): string {
  if (s === "sika") return "Sika";
  if (s === "sikadp") return "Combinat";
  return "Adeplast";
}

function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtRo(n: number, frac = 0): string {
  return new Intl.NumberFormat("ro-RO", {
    maximumFractionDigits: frac, minimumFractionDigits: frac,
  }).format(n);
}

function fmtPct(n: number, frac = 1): string {
  return `${n >= 0 ? "" : "−"}${Math.abs(n).toLocaleString("ro-RO", {
    minimumFractionDigits: frac, maximumFractionDigits: frac,
  })}%`;
}

function shiftMonths(year: number, month: number, delta: number): { y: number; m: number } {
  const total = year * 12 + (month - 1) + delta;
  return { y: Math.floor(total / 12), m: (total % 12) + 1 };
}

function defaultPeriod(): { fromYear: number; fromMonth: number; toYear: number; toMonth: number } {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const start = shiftMonths(year, month, -5);
  return { fromYear: start.y, fromMonth: start.m, toYear: year, toMonth: month };
}


export default function MarjaLunaraPage() {
  const { scope: companyScope } = useCompanyScope();
  const [scope, setScope] = useState<MLScope>(scopeFromCompany(companyScope));
  const init = defaultPeriod();
  const [fromYear, setFromYear] = useState(init.fromYear);
  const [fromMonth, setFromMonth] = useState(init.fromMonth);
  const [toYear, setToYear] = useState(init.toYear);
  const [toMonth, setToMonth] = useState(init.toMonth);

  const [data, setData] = useState<MarjaLunaraResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setScope(scopeFromCompany(companyScope));
  }, [companyScope]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMarjaLunara(scope, fromYear, fromMonth, toYear, toMonth)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError) setError(e.message);
        else if (e instanceof Error) setError(e.message);
        else setError("Eroare la incarcare");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [scope, fromYear, fromMonth, toYear, toMonth]);

  const yearsOptions = useMemo(() => {
    const cy = new Date().getFullYear();
    return [cy - 3, cy - 2, cy - 1, cy];
  }, []);

  const scopeOptions: MLScope[] = companyScope === "sikadp"
    ? ["adp", "sika", "sikadp"]
    : companyScope === "sika"
      ? ["sika"]
      : ["adp"];

  const fallbackMonths = data?.months.filter((m) => toNum(m.fallbackRevenuePct) > 0) ?? [];

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>Analiza Marja Lunara — {scopeLabel(scope)}</div>
      <div style={styles.sectionSubtitle}>
        Marja per (luna, grupa) folosind costul SNAPSHOT al lunii respective
        (din meniul Pret Productie · Pe Luna). Lunile fara snapshot folosesc
        pretul mediu ca fallback — sunt marcate cu disclaimer.
      </div>

      <div style={styles.controls}>
        {scopeOptions.length > 1 && (
          <div style={styles.tabs}>
            {scopeOptions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScope(s)}
                style={{ ...styles.tabBtn, ...(scope === s ? styles.tabBtnActive : {}) }}
              >
                {scopeLabel(s)}
              </button>
            ))}
          </div>
        )}

        <div style={styles.periodGroup}>
          <span style={styles.periodLabel}>De la</span>
          <PeriodSelect
            year={fromYear} month={fromMonth} years={yearsOptions}
            onChange={(y, m) => { setFromYear(y); setFromMonth(m); }}
          />
          <span style={styles.periodLabel}>pana la</span>
          <PeriodSelect
            year={toYear} month={toMonth} years={yearsOptions}
            onChange={(y, m) => { setToYear(y); setToMonth(m); }}
          />
        </div>
      </div>

      {fallbackMonths.length > 0 && (
        <div style={styles.disclaimerBox}>
          ⚠ <strong>Disclaimer:</strong> {fallbackMonths.length} luna(i) folosesc
          pretul mediu ca fallback — nu au snapshot lunar incarcat: {" "}
          {fallbackMonths.map((m) => `${MONTH_NAMES[m.month]} ${m.year}`).join(", ")}.
          Incarca cost lunar din meniul "Pret Productie" tab "Pe Luna" pentru
          masuratori instantanee.
        </div>
      )}

      {loading && <div style={styles.muted}>Se calculeaza...</div>}
      {error && (
        <div style={styles.errorBox}><strong>Eroare:</strong> {error}</div>
      )}

      {!loading && data && data.months.length > 0 && (
        <>
          <MonthlySummaryTable months={data.months} />
          <MarginChart months={data.months} />
          <MonthlyGroupsMatrix months={data.months} scope={scope} />
        </>
      )}
    </div>
  );
}


function PeriodSelect({
  year, month, years, onChange,
}: {
  year: number; month: number; years: number[];
  onChange: (y: number, m: number) => void;
}) {
  return (
    <span style={{ display: "inline-flex", gap: 6 }}>
      <select value={month} onChange={(e) => onChange(year, Number(e.target.value))} style={styles.select}>
        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
          <option key={m} value={m}>{MONTH_NAMES[m]}</option>
        ))}
      </select>
      <select value={year} onChange={(e) => onChange(Number(e.target.value), month)} style={styles.select}>
        {years.map((y) => (<option key={y} value={y}>{y}</option>))}
      </select>
    </span>
  );
}


function MonthlySummaryTable({ months }: { months: MLMonthRow[] }) {
  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>Sumar lunar</div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Luna</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Revenue</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Cost</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Profit brut</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Marja brut</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Discount</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Profit net</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Marja neta</th>
            <th style={{ ...styles.th, textAlign: "center" }}>Sursa cost</th>
          </tr>
        </thead>
        <tbody>
          {months.map((m, i) => {
            const prev = i > 0 ? months[i - 1] : null;
            const margin = toNum(m.marginPct);
            const marginNet = toNum(m.marginPctNet);
            const tone = marginNet >= 30 ? "var(--green)" : marginNet >= 15 ? "var(--orange)" : "var(--red)";
            const deltaNet = prev ? toNum(m.marginPctNet) - toNum(prev.marginPctNet) : null;
            const fallbackPct = toNum(m.fallbackRevenuePct);
            const sourceLabel = fallbackPct === 0
              ? "Snapshot lunar"
              : fallbackPct >= 100
                ? "⚠ Pret mediu"
                : `Mixt (${fmtPct(100 - fallbackPct, 0)} snapshot)`;
            return (
              <tr key={`${m.year}-${m.month}`}>
                <td style={{ ...styles.td, fontWeight: 600 }}>
                  {MONTH_NAMES[m.month]} {m.year}
                </td>
                <td style={styles.tdNum}>{fmtRo(toNum(m.revenuePeriod), 0)}</td>
                <td style={styles.tdNum}>{fmtRo(toNum(m.costTotal), 0)}</td>
                <td style={{ ...styles.tdNum, color: toNum(m.profitTotal) >= 0 ? "var(--green)" : "var(--red)" }}>
                  {fmtRo(toNum(m.profitTotal), 0)}
                </td>
                <td style={styles.tdNum}>{fmtPct(margin, 1)}</td>
                <td style={{ ...styles.tdNum, color: toNum(m.discountAllocatedTotal) < 0 ? "var(--red)" : "var(--muted)" }}>
                  {toNum(m.discountAllocatedTotal) === 0 ? "—" : fmtRo(toNum(m.discountAllocatedTotal), 0)}
                </td>
                <td style={{ ...styles.tdNum, color: toNum(m.profitNetTotal) >= 0 ? "var(--green)" : "var(--red)" }}>
                  {fmtRo(toNum(m.profitNetTotal), 0)}
                </td>
                <td style={{ ...styles.tdNum, color: tone, fontWeight: 700 }}>
                  {fmtPct(marginNet, 1)}
                  {deltaNet !== null && (
                    <span style={{
                      marginLeft: 6, fontSize: 10, fontWeight: 500,
                      color: deltaNet >= 0 ? "var(--green)" : "var(--red)",
                    }}>
                      ({deltaNet >= 0 ? "+" : ""}{deltaNet.toFixed(1)}pp)
                    </span>
                  )}
                </td>
                <td style={{
                  ...styles.td, textAlign: "center", fontSize: 11,
                  color: fallbackPct === 0 ? "var(--green)" : "var(--orange)",
                }}>
                  {sourceLabel}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


function MarginChart({ months }: { months: MLMonthRow[] }) {
  // Linie simpla SVG: marja netă (%) lunar
  const W = 720;
  const H = 200;
  const PAD = 30;

  if (months.length === 0) return null;

  const values = months.map((m) => toNum(m.marginPctNet));
  const minV = Math.min(0, ...values);
  const maxV = Math.max(50, ...values);
  const x = (i: number) => PAD + (i / Math.max(1, months.length - 1)) * (W - 2 * PAD);
  const y = (v: number) => PAD + (1 - (v - minV) / (maxV - minV)) * (H - 2 * PAD);

  const path = values
    .map((v, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`)
    .join(" ");

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>Evolutie Marja Neta (%)</div>
      <svg width={W} height={H} style={{ maxWidth: "100%", height: "auto" }}>
        <line x1={PAD} y1={y(0)} x2={W - PAD} y2={y(0)} stroke="rgba(255,255,255,0.1)" strokeDasharray="2 2" />
        <path d={path} fill="none" stroke="var(--cyan)" strokeWidth={2} />
        {values.map((v, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(v)} r={4} fill="var(--cyan)" />
            <text x={x(i)} y={y(v) - 8} fill="var(--text)" fontSize={10} textAnchor="middle">
              {v.toFixed(1)}%
            </text>
            <text x={x(i)} y={H - 8} fill="var(--muted)" fontSize={10} textAnchor="middle">
              {MONTH_NAMES[months[i].month]} '{months[i].year.toString().slice(-2)}
            </text>
            {months[i].fallbackRevenuePct && toNum(months[i].fallbackRevenuePct) > 0 && (
              <text x={x(i)} y={y(v) + 14} fill="var(--orange)" fontSize={9} textAnchor="middle">
                ⚠
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}


function MonthlyGroupsMatrix({
  months, scope,
}: { months: MLMonthRow[]; scope: MLScope }) {
  // Toate grupele care apar in macar o luna.
  const allGroups = useMemo(() => {
    const seen = new Map<string, { kind: string; key: string; label: string }>();
    for (const m of months) {
      for (const g of m.groups) {
        const k = `${g.kind}::${g.key}`;
        if (!seen.has(k)) seen.set(k, { kind: g.kind, key: g.key, label: g.label });
      }
    }
    return Array.from(seen.values());
  }, [months]);

  if (allGroups.length === 0) return null;

  const groupNoun = scope === "sika" ? "TM" : scope === "sikadp" ? "Categorie / TM" : "Categorie";

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>Marja Neta pe {groupNoun} × Luna</div>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>{groupNoun}</th>
              {months.map((m) => (
                <th key={`${m.year}-${m.month}`} style={{ ...styles.th, textAlign: "right" }}>
                  {MONTH_NAMES[m.month]} '{m.year.toString().slice(-2)}
                  {toNum(m.fallbackRevenuePct) > 0 && (
                    <span title="Foloseste pret mediu ca fallback" style={{ color: "var(--orange)" }}> ⚠</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {allGroups.map((g) => (
              <tr key={`${g.kind}::${g.key}`}>
                <td style={{ ...styles.td, fontWeight: 600 }}>{g.label}</td>
                {months.map((m) => {
                  const found = m.groups.find((mg) => mg.kind === g.kind && mg.key === g.key);
                  if (!found) {
                    return <td key={`${m.year}-${m.month}`} style={{ ...styles.tdNum, color: "var(--muted)" }}>—</td>;
                  }
                  const mn = toNum(found.marginPctNet);
                  const tone = mn >= 30 ? "var(--green)" : mn >= 15 ? "var(--orange)" : "var(--red)";
                  return (
                    <td key={`${m.year}-${m.month}`} style={{ ...styles.tdNum, color: tone, fontWeight: 600 }}>
                      {fmtPct(mn, 1)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 16 },
  sectionTitle: { fontSize: 20, fontWeight: 700 },
  sectionSubtitle: { fontSize: 12, color: "var(--muted)", marginTop: -8, lineHeight: 1.5 },
  controls: { display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" },
  tabs: { display: "flex", gap: 6 },
  tabBtn: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "6px 14px",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  tabBtnActive: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
  },
  periodGroup: { display: "flex", gap: 6, alignItems: "center" },
  periodLabel: { fontSize: 12, color: "var(--muted)" },
  select: {
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "5px 10px",
    borderRadius: 6,
    fontSize: 13,
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  cardTitle: { fontSize: 14, fontWeight: 700 },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 12,
    borderRadius: 8,
    fontSize: 13,
  },
  disclaimerBox: {
    background: "rgba(251,146,60,0.08)",
    border: "1px solid var(--orange)",
    color: "var(--orange)",
    padding: 12,
    borderRadius: 8,
    fontSize: 12,
    lineHeight: 1.5,
  },
  muted: { color: "var(--muted)", fontSize: 13 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: {
    borderBottom: "1px solid var(--border)",
    padding: "8px 10px",
    textAlign: "left",
    fontSize: 11,
    fontWeight: 700,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  td: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 10px",
    color: "var(--text)",
  },
  tdNum: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 10px",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    color: "var(--text)",
  },
};
