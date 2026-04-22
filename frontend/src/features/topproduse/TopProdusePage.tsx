import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { ApiError } from "../../shared/api";
import { getTopProduse } from "./api";
import type {
  TopProduseProductRow,
  TopProduseResponse,
  TopProduseScope,
  TopProduseTotals,
} from "./types";

function scopeFromCompany(c: CompanyScope): TopProduseScope {
  return c === "adeplast" ? "adp" : (c as TopProduseScope);
}

function scopeLabel(s: TopProduseScope): string {
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

function fmtDec(n: number): string {
  return new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(n);
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

export default function TopProdusePage() {
  const { group: groupParam } = useParams<{ group: string }>();
  const navigate = useNavigate();
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [limit, setLimit] = useState<number>(20);
  const [data, setData] = useState<TopProduseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const group = (groupParam ?? "EPS").toUpperCase();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getTopProduse({ scope: apiScope, group, year, limit })
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
  }, [apiScope, group, year, limit]);

  function onChangeGroup(newCode: string) {
    navigate(`/topprod/${encodeURIComponent(newCode)}`);
  }

  const MONTH_ABBR = [
    "ian", "feb", "mar", "apr", "mai", "iun",
    "iul", "aug", "sep", "oct", "nov", "dec",
  ];
  const ytdLabel = data?.ytdMonths && data.ytdMonths.length > 0
    ? data.ytdMonths.map((m) => MONTH_ABBR[m - 1]).join("·")
    : null;

  return (
    <div style={{ ...styles.page, zoom: 0.80 as unknown as number }}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          🏆 {scopeLabel(apiScope)} · Top {data?.limit ?? limit} ·{" "}
          {data?.groupLabel ?? group}{" "}
          <span style={{ color: "var(--muted)", fontWeight: 400 }}>
            {ytdLabel
              ? `YTD ${ytdLabel} · ${data?.yearCurr ?? year} vs ${data?.yearPrev ?? year - 1}`
              : `(${data?.yearPrev ?? year - 1} vs ${data?.yearCurr ?? year})`}
          </span>
        </h1>
        <div style={styles.controls}>
          {data && (
            <GroupSelector
              value={group}
              options={data.availableCategories}
              onChange={onChangeGroup}
            />
          )}
          <LimitSelector value={limit} onChange={setLimit} />
          <YearSelector value={year} onChange={setYear} />
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {data && (
        <TopProductsCard
          title={`Top ${data.limit} produse din grupa ${data.groupLabel}`}
          products={data.products}
          totals={data.totals}
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
      style={styles.select}
    >
      {options.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </select>
  );
}

function LimitSelector({
  value,
  onChange,
}: {
  value: number;
  onChange: (n: number) => void;
}) {
  const options = [10, 15, 20, 30, 50, 100];
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      style={styles.select}
      title="Numărul de produse în top"
    >
      {options.map((n) => (
        <option key={n} value={n}>
          Top {n}
        </option>
      ))}
    </select>
  );
}

function GroupSelector({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { code: string; label: string }[];
  onChange: (code: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={styles.select}
    >
      {options.map((c) => (
        <option key={c.code} value={c.code}>
          {c.label} ({c.code})
        </option>
      ))}
    </select>
  );
}

function TopProductsCard({
  title,
  products,
  totals,
  yearPrev,
  yearCurr,
}: {
  title: string;
  products: TopProduseProductRow[];
  totals: TopProduseTotals;
  yearPrev: number;
  yearCurr: number;
}) {
  const totalPctTone = pctTone(totals.pct);
  const totalPctFmt = fmtPctSigned(totals.pct) ?? "—";

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>{title}</h2>
        <PctBadge tone={totalPctTone} size="lg">
          {totalPctFmt}
        </PctBadge>
      </div>

      {products.length === 0 ? (
        <div style={styles.empty}>Nu există produse în top pentru această grupă.</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          {(() => {
            const maxSales = Math.max(
              ...products.map((p) => toNum(p.salesY2)), 1,
            );
            return (
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th style={{ ...styles.th, width: 28 }}>#</th>
                    <th style={styles.th}>Produs</th>
                    <th style={{ ...styles.th, width: 140 }}>Volum {yearCurr}</th>
                    <th style={styles.thNum}>{yearPrev}</th>
                    <th style={styles.thNum}>{yearCurr}</th>
                    <th style={styles.thNum}>Δ</th>
                    <th style={{ ...styles.thNum, width: 60 }}>%</th>
                    <th style={styles.thNum}>Cant {yearPrev}→{yearCurr}</th>
                    <th style={styles.thNum}>Preț {yearPrev}→{yearCurr}</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => {
                    const y2 = toNum(p.salesY2);
                    const barPct = (y2 / maxSales) * 100;
                    return (
                      <tr key={p.productId}>
                        <td style={styles.tdRank}>{p.rank}</td>
                        <td style={styles.td} title={p.productName}>
                          {p.productName.length > 55
                            ? `${p.productName.slice(0, 55)}…`
                            : p.productName}
                        </td>
                        <td style={styles.tdBar}>
                          <div style={styles.barTrack}>
                            <div style={{
                              ...styles.barFill,
                              width: `${barPct}%`,
                              background: pctTone(p.pct) === "neg"
                                ? "var(--red,#dc2626)" : "var(--green,#16a34a)",
                            }} />
                          </div>
                        </td>
                        <td style={styles.tdNumMuted}>{fmtRo(toNum(p.salesY1))}</td>
                        <td style={{ ...styles.tdNum, fontWeight: 600 }}>
                          {fmtRo(y2)}
                        </td>
                        <td style={styles.tdNum}>
                          <DiffPill value={toNum(p.diff)} />
                        </td>
                        <td style={styles.tdNum}>
                          <PctBadge tone={pctTone(p.pct)} size="md">
                            {fmtPctSigned(p.pct) ?? "—"}
                          </PctBadge>
                        </td>
                        <td style={styles.tdNumMuted}>
                          {fmtRo(toNum(p.qtyY1))} → <b style={{ color: "var(--text)" }}>
                            {fmtRo(toNum(p.qtyY2))}
                          </b>
                        </td>
                        <td style={styles.tdNumMuted}>
                          {p.priceY1 != null ? fmtDec(toNum(p.priceY1)) : "—"}
                          {" → "}
                          <b style={{ color: "var(--text)" }}>
                            {p.priceY2 != null ? fmtDec(toNum(p.priceY2)) : "—"}
                          </b>
                        </td>
                      </tr>
                    );
                  })}
                  <tr style={styles.totalRow}>
                    <td style={styles.tdTotal} colSpan={3}>TOTAL TOP</td>
                    <td style={styles.tdNumTotal}>{fmtRo(toNum(totals.salesY1))}</td>
                    <td style={styles.tdNumTotal}>{fmtRo(toNum(totals.salesY2))}</td>
                    <td style={styles.tdNumTotal}>
                      <DiffPill value={toNum(totals.diff)} />
                    </td>
                    <td style={styles.tdNumTotal}>
                      <PctBadge tone={totalPctTone} size="md">
                        {totalPctFmt}
                      </PctBadge>
                    </td>
                    <td style={styles.tdNumTotal}>
                      {fmtRo(toNum(totals.qtyY1))} → {fmtRo(toNum(totals.qtyY2))}
                    </td>
                    <td style={styles.tdNumTotal}>—</td>
                  </tr>
                </tbody>
              </table>
            );
          })()}
        </div>
      )}
    </div>
  );
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
  controls: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  select: {
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
  empty: { color: "var(--muted)", padding: 24, textAlign: "center" },
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
  tdMuted: {
    padding: "7px 8px",
    fontSize: 12,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    whiteSpace: "nowrap",
    fontVariantNumeric: "tabular-nums",
  },
  tdRank: {
    padding: "7px 4px",
    fontSize: 12,
    fontWeight: 700,
    color: "var(--muted)",
    textAlign: "center",
    borderBottom: "1px solid var(--border)",
    fontVariantNumeric: "tabular-nums",
  },
  tdBar: {
    padding: "7px 8px",
    borderBottom: "1px solid var(--border)",
    minWidth: 120,
  },
  barTrack: {
    height: 8,
    background: "var(--bg-elevated,#eee)",
    borderRadius: 2,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    transition: "width 0.2s",
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
  tdNumMuted: {
    padding: "7px 8px",
    fontSize: 13,
    color: "var(--muted)",
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
