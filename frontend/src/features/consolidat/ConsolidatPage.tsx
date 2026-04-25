import { useEffect, useState, type CSSProperties } from "react";

import { Skeleton } from "../../shared/ui/Skeleton";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getConsolidatAgentStores, getConsolidatKa } from "./api";
import type {
  ConsolidatAgentRow,
  ConsolidatKaResponse,
  ConsolidatStoreRow,
} from "./types";

/**
 * Consolidat KA — replica 1:1 a paginii "Consolidat" din adeplast-dashboard
 * legacy. Layout: header cu period + badge → tabel companie cu progress
 * bar integrat → 4 KPI cards mari → tabel per agent cu expand arrow.
 *
 * Scope-ul companiei vine din CompanyScopeProvider (switcher-ul de sus).
 */

function toNum(s: string | number): number {
  const n = typeof s === "number" ? s : parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}
function fmtRo(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}
function fmtM(n: number): string {
  const m = n / 1_000_000;
  const sign = m < 0 ? "-" : "";
  return `${sign}${Math.abs(m).toFixed(2)} M`;
}
function fmtPct(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}
function signNum(n: number): string {
  return `${n > 0 ? "+" : ""}${fmtRo(n)}`;
}

export default function ConsolidatPage() {
  const { scope } = useCompanyScope();
  const [data, setData] = useState<ConsolidatKaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getConsolidatKa({ company: scope })
      .then((resp) => {
        if (!cancelled) setData(resp);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message || "Eroare la încărcare");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope]);

  if (loading) {
    return (
      <div style={styles.page}>
        <Skeleton height={36} />
        <Skeleton height={80} />
        <div style={styles.kpiRow}>
          <Skeleton height={120} />
          <Skeleton height={120} />
          <Skeleton height={120} />
          <Skeleton height={120} />
        </div>
        <Skeleton height={260} />
      </div>
    );
  }
  if (error) {
    return <div style={styles.errorBox}>Eroare: {error}</div>;
  }
  if (!data) return null;

  const y1 = data.y1;
  const y2 = data.y2;
  const salesY1 = toNum(data.totals.salesY1);
  const salesY2 = toNum(data.totals.salesY2);
  const diff = toNum(data.totals.diff);
  const pct = data.totals.pct;

  return (
    <div style={styles.page}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={styles.headerRow}>
        <span style={styles.titleIcon}>📊</span>
        <h1 style={styles.title}>Consolidat KA</h1>
        <span style={styles.periodLabel}>{data.periodLabel}</span>
        {data.includeCurrentMonth && (
          <span style={styles.includeCurrent}>include luna curentă</span>
        )}
      </div>

      {/* ── Tabel companie cu progress bar ───────────────────── */}
      <div style={styles.tableCard}>
        <div style={styles.tableHeaderRow}>
          <div style={styles.thCompanie}>COMPANIE</div>
          <div style={styles.thNum}>Vânzări {y1}</div>
          <div style={styles.thNum}>Vânzări {y2}</div>
          <div style={styles.thBar} />
          <div style={styles.thNumRight}>Diferență</div>
          <div style={styles.thVariatie}>Variație</div>
        </div>
        <div style={styles.tableRow}>
          <div style={styles.tdCompanie}>
            <span style={styles.companyDot} />
            <span style={styles.companyName}>{data.companyLabel}</span>
          </div>
          <div style={styles.tdNumMuted}>{fmtRo(salesY1)}</div>
          <div style={styles.tdNumAccent}>{fmtRo(salesY2)}</div>
          <div style={styles.tdBar}>
            <ProgressBarRow y1={salesY1} y2={salesY2} />
          </div>
          <div
            style={{
              ...styles.tdNumRight,
              color: diff < 0 ? "var(--red)" : "var(--green)",
            }}
          >
            {signNum(diff)}
          </div>
          <div style={styles.tdVariatie}>
            <PctPill pct={pct} />
          </div>
        </div>
      </div>

      {/* ── 4 KPI cards ────────────────────────────────────────── */}
      <div style={styles.kpiRow}>
        <KpiBig label={`VÂNZĂRI ${y2}`} value={fmtM(salesY2)} sub="RON" />
        <KpiBig label={`VÂNZĂRI ${y1}`} value={fmtM(salesY1)} sub="RON" muted />
        <KpiBig
          label="DIFERENȚĂ"
          value={fmtM(diff)}
          sub="RON"
          valueColor={diff < 0 ? "var(--red)" : "var(--green)"}
        />
        <KpiBig
          label="VARIAȚIE %"
          value={fmtPct(pct)}
          sub={`${y2} vs ${y1}`}
          valueColor={pct < 0 ? "var(--red)" : "var(--green)"}
        />
      </div>

      {/* ── Tabel per Agent ────────────────────────────────────── */}
      <div style={styles.headerRow}>
        <span style={styles.titleIcon}>👥</span>
        <h2 style={styles.subTitle}>
          Consolidat per Agent {capitalize(data.company)}
        </h2>
      </div>
      <AgentsTable y1={y1} y2={y2} rows={data.byAgent} company={data.company} />
    </div>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function ProgressBarRow({ y1, y2 }: { y1: number; y2: number }) {
  const max = Math.max(y1, y2, 1);
  const y2Ratio = Math.max(0, Math.min(100, (y2 / max) * 100));
  return (
    <div style={styles.barOuter}>
      <div
        style={{
          ...styles.barInner,
          width: `${y2Ratio}%`,
        }}
      />
    </div>
  );
}

function PctPill({ pct }: { pct: number }) {
  const isNeg = pct < 0;
  return (
    <span
      style={{
        ...styles.pctPill,
        background: isNeg ? "rgba(239,68,68,0.15)" : "rgba(52,211,153,0.15)",
        color: isNeg ? "var(--red)" : "var(--green)",
      }}
    >
      {isNeg ? "▼" : "▲"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function KpiBig({
  label,
  value,
  sub,
  valueColor,
  muted,
}: {
  label: string;
  value: string;
  sub: string;
  valueColor?: string;
  muted?: boolean;
}) {
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{label}</div>
      <div
        style={{
          ...styles.kpiValue,
          color: valueColor ?? (muted ? "var(--muted)" : "var(--text)"),
        }}
      >
        {value}
      </div>
      <div style={styles.kpiSub}>{sub}</div>
    </div>
  );
}

function AgentsTable({
  y1,
  y2,
  rows,
  company,
}: {
  y1: number;
  y2: number;
  rows: ConsolidatAgentRow[];
  company: "adeplast" | "sika" | "sikadp";
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [storesByAgent, setStoresByAgent] = useState<
    Record<string, { loading: boolean; error?: string; rows?: ConsolidatStoreRow[] }>
  >({});

  if (rows.length === 0) {
    return (
      <div style={styles.emptyBox}>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Nu sunt date pentru perioada selectată.
        </p>
      </div>
    );
  }

  // Total general = sumă pe toți agenții.
  const totalY1 = rows.reduce((a, r) => a + toNum(r.salesY1), 0);
  const totalY2 = rows.reduce((a, r) => a + toNum(r.salesY2), 0);
  const totalDiff = totalY2 - totalY1;
  const totalPct = totalY1 === 0 ? 0 : ((totalY2 - totalY1) / totalY1) * 100;
  const totalStores = rows.reduce((a, r) => a + r.storesCount, 0);

  function loadStores(id: string, agentId: string | null) {
    setStoresByAgent((prev) => ({ ...prev, [id]: { loading: true } }));
    getConsolidatAgentStores(agentId, { company })
      .then((resp) => {
        setStoresByAgent((prev) => ({
          ...prev,
          [id]: { loading: false, rows: resp.stores },
        }));
      })
      .catch((e: Error) => {
        setStoresByAgent((prev) => ({
          ...prev,
          [id]: { loading: false, error: e.message || "Eroare" },
        }));
      });
  }

  function toggle(id: string, agentId: string | null) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        if (!storesByAgent[id]) loadStores(id, agentId);
      }
      return next;
    });
  }

  return (
    <div style={styles.tableCard}>
      <div style={styles.agentHeaderRow}>
        <div style={styles.thAgent}>AGENT</div>
        <div style={styles.thMag}>Mag.</div>
        <div style={styles.thNum}>{y1}</div>
        <div style={styles.thNum}>{y2}</div>
        <div style={styles.thNumRight}>Gap</div>
        <div style={styles.thPct}>%</div>
      </div>
      {/* Total general — sumă pe toți agenții */}
      <div style={styles.agentTotalRow}>
        <div style={styles.tdAgent}>
          <span style={{ ...styles.expandArrow, visibility: "hidden" }}>▶</span>
          <span style={styles.totalLabel}>TOTAL GENERAL</span>
        </div>
        <div style={{ ...styles.tdMag, fontWeight: 700, color: "var(--text)" }}>
          {totalStores}
        </div>
        <div style={{ ...styles.tdNumMuted, fontWeight: 700, color: "var(--text)" }}>
          {fmtRo(totalY1)}
        </div>
        <div style={{ ...styles.tdNumAccent, fontWeight: 800 }}>{fmtRo(totalY2)}</div>
        <div
          style={{
            ...styles.tdNumRight,
            fontWeight: 800,
            color: totalDiff < 0 ? "var(--red)" : "var(--green)",
          }}
        >
          {signNum(totalDiff)}
        </div>
        <div style={styles.tdPct}>
          <PctPill pct={totalPct} />
        </div>
      </div>
      {rows.map((r, idx) => {
        const id = r.agentId ?? `nomap-${idx}`;
        const isOpen = expanded.has(id);
        const y1n = toNum(r.salesY1);
        const y2n = toNum(r.salesY2);
        const diffn = toNum(r.diff);
        const storesState = storesByAgent[id];
        return (
          <div key={id} className="agent-section">
            <div
              style={styles.agentRow}
              onClick={() => toggle(id, r.agentId)}
              role="button"
              tabIndex={0}
            >
              <div style={styles.tdAgent}>
                <span
                  style={{
                    ...styles.expandArrow,
                    transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                  }}
                >
                  ▶
                </span>
                <span style={styles.agentName}>{r.name}</span>
              </div>
              <div style={styles.tdMag}>{r.storesCount}</div>
              <div style={styles.tdNumMuted}>{fmtRo(y1n)}</div>
              <div style={styles.tdNumAccent}>{fmtRo(y2n)}</div>
              <div
                style={{
                  ...styles.tdNumRight,
                  color: diffn < 0 ? "var(--red)" : "var(--green)",
                }}
              >
                {signNum(diffn)}
              </div>
              <div style={styles.tdPct}>
                <PctPill pct={r.pct} />
              </div>
            </div>
            {isOpen && (
              <StoresDrilldown y1={y1} y2={y2} state={storesState} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function StoresDrilldown({
  y1,
  y2,
  state,
}: {
  y1: number;
  y2: number;
  state: { loading: boolean; error?: string; rows?: ConsolidatStoreRow[] } | undefined;
}) {
  if (!state || state.loading) {
    return (
      <div style={styles.agentDetails}>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>Se încarcă magazinele…</span>
      </div>
    );
  }
  if (state.error) {
    return (
      <div style={styles.agentDetails}>
        <span style={{ color: "var(--red)", fontSize: 12 }}>Eroare: {state.error}</span>
      </div>
    );
  }
  const rows = state.rows ?? [];
  if (rows.length === 0) {
    return (
      <div style={styles.agentDetails}>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          Nu există magazine pentru acest agent în perioada selectată.
        </span>
      </div>
    );
  }
  return (
    <div style={styles.storesDetails}>
      <div style={styles.storeHeaderRow}>
        <div>MAGAZIN</div>
        <div style={{ textAlign: "left" }}>{y1}</div>
        <div style={{ textAlign: "left" }}>{y2}</div>
        <div style={{ textAlign: "right" }}>Gap</div>
        <div style={{ textAlign: "right" }}>%</div>
      </div>
      {rows.map((s, i) => {
        const sy1 = toNum(s.salesY1);
        const sy2 = toNum(s.salesY2);
        const sdiff = toNum(s.diff);
        return (
          <div key={s.storeId ?? `nomap-${i}`} style={styles.storeRow}>
            <div style={styles.storeName} title={s.name}>
              {s.name}
            </div>
            <div style={styles.tdNumMuted}>{fmtRo(sy1)}</div>
            <div style={styles.tdNumAccent}>{fmtRo(sy2)}</div>
            <div
              style={{
                ...styles.tdNumRight,
                color: sdiff < 0 ? "var(--red)" : "var(--green)",
              }}
            >
              {signNum(sdiff)}
            </div>
            <div style={{ textAlign: "right" }}>
              <PctPill pct={s.pct} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 10 },
  headerRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  titleIcon: { fontSize: 18 },
  title: {
    fontSize: 20,
    fontWeight: 700,
    color: "var(--cyan)",
    margin: 0,
  },
  subTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--cyan)",
    margin: 0,
  },
  periodLabel: { fontSize: 13, color: "var(--muted)" },
  includeCurrent: {
    background: "rgba(251,146,60,0.15)",
    color: "var(--orange)",
    border: "1px solid rgba(251,146,60,0.35)",
    padding: "3px 10px",
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
  },
  tableCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    overflow: "hidden",
  },
  tableHeaderRow: {
    display: "grid",
    gridTemplateColumns: "1.5fr 1fr 1fr 1.2fr 1fr 0.8fr",
    gap: 14,
    padding: "5px 16px",
    borderBottom: "1px solid var(--border)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
  },
  tableRow: {
    display: "grid",
    gridTemplateColumns: "1.5fr 1fr 1fr 1.2fr 1fr 0.8fr",
    gap: 14,
    padding: "6px 16px",
    alignItems: "center",
  },
  thCompanie: {},
  thNum: { textAlign: "left" },
  thNumRight: { textAlign: "right" },
  thBar: {},
  thVariatie: { textAlign: "right" },
  tdCompanie: { display: "flex", alignItems: "center", gap: 10 },
  companyDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "var(--cyan)",
  },
  companyName: { fontSize: 13, fontWeight: 700, color: "var(--text)" },
  tdNumMuted: { fontSize: 13, color: "var(--muted)" },
  tdNumAccent: { fontSize: 13, fontWeight: 600, color: "var(--cyan)" },
  tdBar: {},
  tdNumRight: { fontSize: 13, fontWeight: 600, textAlign: "right" },
  tdVariatie: { textAlign: "right" },
  barOuter: {
    height: 8,
    background: "rgba(30,41,59,0.6)",
    borderRadius: 5,
    overflow: "hidden",
  },
  barInner: {
    height: "100%",
    background: "linear-gradient(90deg, #3b82f6, #60a5fa)",
    borderRadius: 5,
  },
  pctPill: {
    display: "inline-block",
    padding: "1px 7px",
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 700,
  },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 14,
  },
  kpiCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minHeight: 58,
  },
  kpiLabel: {
    fontSize: 10,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
    marginBottom: 2,
    lineHeight: 1.2,
  },
  kpiValue: { fontSize: 18, fontWeight: 800, lineHeight: 1.15 },
  kpiSub: { fontSize: 10.5, color: "var(--muted)", marginTop: 2, lineHeight: 1.2 },
  agentHeaderRow: {
    display: "grid",
    gridTemplateColumns: "2fr 0.5fr 1fr 1fr 1fr 0.7fr",
    gap: 14,
    padding: "4px 16px",
    borderBottom: "1px solid var(--border)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
  },
  thAgent: {},
  thMag: { textAlign: "center" },
  thPct: { textAlign: "right" },
  agentRow: {
    display: "grid",
    gridTemplateColumns: "2fr 0.5fr 1fr 1fr 1fr 0.7fr",
    gap: 14,
    padding: "3px 16px",
    alignItems: "center",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
    cursor: "pointer",
  },
  tdAgent: { display: "flex", alignItems: "center", gap: 10 },
  expandArrow: {
    fontSize: 10,
    color: "var(--muted)",
    transition: "transform 0.12s ease",
    width: 10,
  },
  agentName: { fontSize: 13, color: "var(--text)", lineHeight: 1.2 },
  tdMag: { textAlign: "center", color: "var(--muted)" },
  tdPct: { textAlign: "right" },
  agentDetails: {
    padding: "4px 40px 6px",
    background: "rgba(0,0,0,0.2)",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
  },
  agentTotalRow: {
    display: "grid",
    gridTemplateColumns: "2fr 0.5fr 1fr 1fr 1fr 0.7fr",
    gap: 14,
    padding: "5px 16px",
    alignItems: "center",
    borderBottom: "2px solid var(--cyan)",
    background: "rgba(34,211,238,0.06)",
  },
  totalLabel: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.08em",
    color: "var(--cyan)",
  },
  storesDetails: {
    padding: "2px 16px 4px 40px",
    background: "rgba(0,0,0,0.2)",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
  },
  storeHeaderRow: {
    display: "grid",
    gridTemplateColumns: "2fr 1fr 1fr 1fr 0.7fr",
    gap: 14,
    padding: "3px 0",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
    borderBottom: "1px solid rgba(30,41,59,0.5)",
  },
  storeRow: {
    display: "grid",
    gridTemplateColumns: "2fr 1fr 1fr 1fr 0.7fr",
    gap: 14,
    padding: "2px 0",
    alignItems: "center",
    fontSize: 12,
    lineHeight: 1.25,
  },
  storeName: {
    color: "var(--text)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  emptyBox: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "32px 20px",
    textAlign: "center",
  },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 16,
    borderRadius: 8,
  },
};
