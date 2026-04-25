import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { Skeleton } from "../../shared/ui/Skeleton";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getVzLaZi, type VzScope } from "./api";
import type { VzAgentRow, VzKpis, VzResponse } from "./types";

/**
 * Vz la zi — raport zilnic exercițiu lună curentă per agent/magazin.
 * 3 perspective (via company switcher):
 *   • SIKA   : 5 KPI (prev / curr / orders / exercițiu V+C / depășit%)
 *   • ADP    : 6 KPI (+ nelivrate + nefacturate + gap), IND banner
 *   • SIKADP : combined (adp+sika) + sub-blocks per companie, agent unificat
 */

function scopeFromCompany(c: CompanyScope): VzScope {
  return c === "adeplast" ? "adp" : (c as VzScope);
}

function toNum(s: string | number | null | undefined): number {
  if (s == null) return 0;
  const n = typeof s === "number" ? s : parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}
function fmtRo(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}
function fmtPct(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}
function pctRealizat(exercitiu: number, prev: number): number {
  if (prev <= 0) return 0;
  return (exercitiu / prev) * 100;
}
function colorForPct(pct: number): string {
  if (pct >= 100) return "var(--green)";
  if (pct >= 50) return "var(--orange)";
  return "var(--red)";
}
function fmtDateRo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("ro-RO", { day: "2-digit", month: "2-digit", year: "numeric" });
}
function fmtDateTimeRo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function VzLaZiPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);
  const [data, setData] = useState<VzResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getVzLaZi({ scope: apiScope })
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
  }, [apiScope]);

  if (loading) {
    return (
      <div style={styles.page}>
        <Skeleton height={42} />
        <div style={styles.kpiRow}>
          <Skeleton height={100} />
          <Skeleton height={100} />
          <Skeleton height={100} />
          <Skeleton height={100} />
          <Skeleton height={100} />
          <Skeleton height={100} />
        </div>
        <Skeleton height={300} />
      </div>
    );
  }
  if (error) {
    return <div style={styles.errorBox}>Eroare: {error}</div>;
  }
  if (!data) return null;

  const title =
    data.scope === "adp"
      ? "Vz la zi — Adeplast"
      : data.scope === "sika"
      ? "Vz la zi — SIKA"
      : "Vz la zi — Consolidat SIKADP";
  const titleIcon = data.scope === "sika" ? "🔵" : data.scope === "sikadp" ? "📊" : "📈";

  return (
    <div style={styles.page}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div style={styles.headerRow}>
        <span style={styles.titleIcon}>{titleIcon}</span>
        <h1 style={styles.title}>{title}</h1>
        <span style={styles.periodLabel}>
          {data.monthName} {data.yearCurr} vs. {data.yearPrev}
        </span>
        {data.lastUpdate && (
          <span style={styles.lastUpdate}>
            ultima actualizare: {fmtDateTimeRo(data.lastUpdate)}
          </span>
        )}
      </div>

      {/* ── Scope-specific content ─────────────────────────────── */}
      {data.scope === "adp" && <AdpView data={data} />}
      {data.scope === "sika" && <SikaView data={data} />}
      {data.scope === "sikadp" && <SikadpView data={data} />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// ADP — 6 KPI + IND banner + agent table
// ──────────────────────────────────────────────────────────────
function AdpView({ data }: { data: VzResponse }) {
  const k = data.kpis!;
  return (
    <>
      <IndBanner
        reportDate={data.reportDate}
        processed={data.indProcessed}
        missing={data.indMissing}
        processedAmount={data.indProcessedAmount}
        missingAmount={data.indMissingAmount}
      />
      <AdpKpis kpis={k} yearPrev={data.yearPrev} yearCurr={data.yearCurr} />
      <AgentsTable agents={data.agents} variant="adp" />
    </>
  );
}

// ──────────────────────────────────────────────────────────────
// SIKA — 5 KPI + agent table
// ──────────────────────────────────────────────────────────────
function SikaView({ data }: { data: VzResponse }) {
  const k = data.kpis!;
  return (
    <>
      {data.reportDate && (
        <div style={styles.reportDateBanner}>
          📅 Comenzi la data: <strong>{fmtDateRo(data.reportDate)}</strong>
        </div>
      )}
      <SikaKpis kpis={k} yearPrev={data.yearPrev} yearCurr={data.yearCurr} />
      <AgentsTable agents={data.agents} variant="sika" />
    </>
  );
}

// ──────────────────────────────────────────────────────────────
// SIKADP — 3 KPI sections + unified agent table
// ──────────────────────────────────────────────────────────────
function SikadpView({ data }: { data: VzResponse }) {
  const comb = data.combined!;
  const adp = data.adeplast!;
  const sk = data.sika!;
  return (
    <>
      <div style={styles.sectionHeader}>
        <span style={styles.titleIcon}>🔶</span>
        <h2 style={styles.subTitle}>Consolidat ADEPLAST + SIKA</h2>
      </div>
      <CombinedKpis kpis={comb.kpis} yearPrev={data.yearPrev} yearCurr={data.yearCurr} />

      <div style={styles.sectionHeader}>
        <span style={styles.titleIcon}>📈</span>
        <h2 style={styles.subTitle}>Adeplast</h2>
      </div>
      <IndBanner
        reportDate={adp.reportDate}
        processed={adp.indProcessed}
        missing={adp.indMissing}
        processedAmount={adp.indProcessedAmount}
        missingAmount={adp.indMissingAmount}
      />
      <AdpKpis kpis={adp.kpis} yearPrev={data.yearPrev} yearCurr={data.yearCurr} />

      <div style={styles.sectionHeader}>
        <span style={styles.titleIcon}>🔵</span>
        <h2 style={styles.subTitle}>SIKA</h2>
      </div>
      {sk.reportDate && (
        <div style={styles.reportDateBanner}>
          📅 Comenzi SIKA la data: <strong>{fmtDateRo(sk.reportDate)}</strong>
        </div>
      )}
      <SikaKpis kpis={sk.kpis} yearPrev={data.yearPrev} yearCurr={data.yearCurr} />

      <div style={styles.sectionHeader}>
        <span style={styles.titleIcon}>👥</span>
        <h2 style={styles.subTitle}>Per Agent — Consolidat</h2>
      </div>
      <AgentsTable agents={comb.agents} variant="sikadp" />
    </>
  );
}

// ──────────────────────────────────────────────────────────────
// IND banner (ADP only)
// ──────────────────────────────────────────────────────────────
function IndBanner({
  reportDate,
  processed,
  missing,
  processedAmount,
  missingAmount,
}: {
  reportDate: string | null;
  processed: number | null;
  missing: number | null;
  processedAmount?: string | null;
  missingAmount?: string | null;
}) {
  const m = missing ?? 0;
  const p = processed ?? 0;
  const total = m + p;
  if (total === 0) return null;
  const pAmt = toNum(processedAmount);
  const mAmt = toNum(missingAmount);
  return (
    <div style={styles.indBanner}>
      <span style={{ fontSize: 16 }}>📅</span>
      <span>
        Comenzi la data: <strong>{fmtDateRo(reportDate)}</strong>
      </span>
      <span style={styles.indDivider}>•</span>
      <span style={{ color: "var(--green)" }}>
        <strong>{p}</strong> procesate cu IND
        {pAmt > 0 && (
          <>
            {" · "}
            <strong>{fmtRo(pAmt)} RON</strong>
          </>
        )}
      </span>
      {m > 0 && (
        <>
          <span style={styles.indDivider}>•</span>
          <span style={{ color: "var(--red)" }}>
            ⚠ <strong>{m}</strong> fără IND
            {mAmt > 0 && (
              <>
                {" · "}
                <strong>{fmtRo(mAmt)} RON</strong>
              </>
            )}
          </span>
        </>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// KPI cards — 3 variants
// ──────────────────────────────────────────────────────────────
function AdpKpis({ kpis, yearPrev, yearCurr }: { kpis: VzKpis; yearPrev: number; yearCurr: number }) {
  const prev = toNum(kpis.prevSales);
  const curr = toNum(kpis.currSales);
  const nel = toNum(kpis.nelivrate);
  const nef = toNum(kpis.nefacturate);
  const ex = toNum(kpis.exercitiu);
  const gap = toNum(kpis.gap);
  const deltaCurr = prev > 0 ? ((curr - prev) / prev) * 100 : 0;
  const realizat = pctRealizat(ex, prev);
  return (
    <div style={styles.kpiRow}>
      <KpiCard label={`LUNA ANTERIOARĂ (${yearPrev})`} value={fmtRo(prev)} sub="RON" muted />
      <KpiCard
        label={`VÂNZĂRI CURENTE (${yearCurr})`}
        value={fmtRo(curr)}
        sub={fmtPct(deltaCurr)}
        valueColor="var(--cyan)"
        subColor={deltaCurr < 0 ? "var(--red)" : "var(--green)"}
      />
      <KpiCard label="NELIVRATE" value={fmtRo(nel)} sub="RON" valueColor="var(--orange)" />
      <KpiCard label="NEFACTURATE" value={fmtRo(nef)} sub="RON" valueColor="var(--orange)" />
      <KpiCard
        label="EXERCIȚIU (V+N+NF)"
        value={fmtRo(ex)}
        sub={`realizat: ${realizat.toFixed(1)}%`}
        valueColor={colorForPct(realizat)}
        subColor={colorForPct(realizat)}
      />
      <KpiCard
        label={gap >= 0 ? "DEPĂȘIT" : "GAP DE ACOPERIT"}
        value={fmtRo(Math.abs(gap))}
        sub="RON"
        valueColor={gap >= 0 ? "var(--green)" : "var(--red)"}
      />
    </div>
  );
}

function SikaKpis({ kpis, yearPrev, yearCurr }: { kpis: VzKpis; yearPrev: number; yearCurr: number }) {
  const prev = toNum(kpis.prevSales);
  const curr = toNum(kpis.currSales);
  const ord = toNum(kpis.ordersTotal);
  const ex = toNum(kpis.exercitiu);
  const gap = toNum(kpis.gap);
  const deltaCurr = prev > 0 ? ((curr - prev) / prev) * 100 : 0;
  const realizat = pctRealizat(ex, prev);
  return (
    <div style={styles.kpiRow}>
      <KpiCard label={`LUNA ANTERIOARĂ (${yearPrev})`} value={fmtRo(prev)} sub="RON" muted />
      <KpiCard
        label={`VÂNZĂRI CURENTE (${yearCurr})`}
        value={fmtRo(curr)}
        sub={fmtPct(deltaCurr)}
        valueColor="var(--cyan)"
        subColor={deltaCurr < 0 ? "var(--red)" : "var(--green)"}
      />
      <KpiCard label="COMENZI DESCHISE" value={fmtRo(ord)} sub="RON" valueColor="var(--orange)" />
      <KpiCard
        label="EXERCIȚIU (V+C)"
        value={fmtRo(ex)}
        sub={`realizat: ${realizat.toFixed(1)}%`}
        valueColor={colorForPct(realizat)}
        subColor={colorForPct(realizat)}
      />
      <KpiCard
        label={gap >= 0 ? "DEPĂȘIT" : "GAP DE ACOPERIT"}
        value={fmtRo(Math.abs(gap))}
        sub="RON"
        valueColor={gap >= 0 ? "var(--green)" : "var(--red)"}
      />
    </div>
  );
}

function CombinedKpis({
  kpis,
  yearPrev,
  yearCurr,
}: {
  kpis: VzKpis;
  yearPrev: number;
  yearCurr: number;
}) {
  // SIKADP combined — aceleași 6 coloane ca ADP (separă N și NF).
  return <AdpKpis kpis={kpis} yearPrev={yearPrev} yearCurr={yearCurr} />;
}

function KpiCard({
  label,
  value,
  sub,
  valueColor,
  subColor,
  muted,
}: {
  label: string;
  value: string;
  sub: string;
  valueColor?: string;
  subColor?: string;
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
      <div style={{ ...styles.kpiSub, color: subColor ?? "var(--muted)" }}>{sub}</div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Agents table — variants: "adp" | "sika" | "sikadp"
// ──────────────────────────────────────────────────────────────
type TableVariant = "adp" | "sika" | "sikadp";

function AgentsTable({
  agents,
  variant,
}: {
  agents: VzAgentRow[];
  variant: TableVariant;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const totals = useMemo(() => {
    return agents.reduce(
      (acc, a) => ({
        prev: acc.prev + toNum(a.prevSales),
        curr: acc.curr + toNum(a.currSales),
        nel: acc.nel + toNum(a.nelivrate),
        nef: acc.nef + toNum(a.nefacturate),
        ord: acc.ord + toNum(a.ordersTotal),
        ex: acc.ex + toNum(a.exercitiu),
        mag: acc.mag + a.storesCount,
      }),
      { prev: 0, curr: 0, nel: 0, nef: 0, ord: 0, ex: 0, mag: 0 },
    );
  }, [agents]);

  if (agents.length === 0) {
    return (
      <div style={styles.emptyBox}>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Nu sunt date pentru perioada selectată.
        </p>
      </div>
    );
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const isSika = variant === "sika";
  // Grid templates — SIKA colapsează N+NF într-o singură coloană "Comenzi".
  const gridTpl = isSika
    ? "2fr 0.5fr 1fr 1fr 1fr 1.1fr 0.7fr"
    : "2fr 0.5fr 1fr 1fr 0.9fr 0.9fr 1.1fr 0.7fr";

  const headerCells = isSika
    ? ["AGENT", "Mag.", "Luna ant.", "Curente", "Comenzi", "Exercițiu", "%"]
    : ["AGENT", "Mag.", "Luna ant.", "Curente", "Nelivr.", "Nefact.", "Exercițiu", "%"];

  const totalRealizat = pctRealizat(totals.ex, totals.prev);

  return (
    <div style={styles.tableCard}>
      <div style={{ ...styles.agentHeaderRow, gridTemplateColumns: gridTpl }}>
        {headerCells.map((c, i) => (
          <div
            key={i}
            style={i === 0 ? undefined : i === 1 ? styles.thCenter : styles.thRight}
          >
            {c}
          </div>
        ))}
      </div>

      {/* Total general */}
      <div style={{ ...styles.agentTotalRow, gridTemplateColumns: gridTpl }}>
        <div style={styles.tdAgent}>
          <span style={{ ...styles.expandArrow, visibility: "hidden" }}>▶</span>
          <span style={styles.totalLabel}>TOTAL GENERAL</span>
        </div>
        <div style={{ ...styles.tdMag, fontWeight: 700, color: "var(--text)" }}>
          {totals.mag}
        </div>
        <div style={{ ...styles.tdNumMuted, fontWeight: 700, color: "var(--text)" }}>
          {fmtRo(totals.prev)}
        </div>
        <div style={{ ...styles.tdNumAccent, fontWeight: 800 }}>{fmtRo(totals.curr)}</div>
        {isSika ? (
          <div style={{ ...styles.tdNumRight, fontWeight: 700, color: "var(--orange)" }}>
            {fmtRo(totals.ord)}
          </div>
        ) : (
          <>
            <div style={{ ...styles.tdNumRight, fontWeight: 700, color: "var(--orange)" }}>
              {fmtRo(totals.nel)}
            </div>
            <div style={{ ...styles.tdNumRight, fontWeight: 700, color: "var(--orange)" }}>
              {fmtRo(totals.nef)}
            </div>
          </>
        )}
        <div
          style={{
            ...styles.tdNumRight,
            fontWeight: 800,
            color: colorForPct(totalRealizat),
          }}
        >
          {fmtRo(totals.ex)}
        </div>
        <div style={styles.tdPct}>
          <PctPill pct={totalRealizat} />
        </div>
      </div>

      {agents.map((a, idx) => {
        const id = a.agentId ?? `nomap-${idx}`;
        const isOpen = expanded.has(id);
        const prev = toNum(a.prevSales);
        const curr = toNum(a.currSales);
        const nel = toNum(a.nelivrate);
        const nef = toNum(a.nefacturate);
        const ord = toNum(a.ordersTotal);
        const ex = toNum(a.exercitiu);
        const realizat = pctRealizat(ex, prev);
        return (
          <div key={id} className="agent-section">
            <div
              style={{ ...styles.agentRow, gridTemplateColumns: gridTpl }}
              onClick={() => toggle(id)}
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
                <span style={styles.agentName}>{a.agentName}</span>
              </div>
              <div style={styles.tdMag}>{a.storesCount}</div>
              <div style={styles.tdNumMuted}>{fmtRo(prev)}</div>
              <div style={styles.tdNumAccent}>{fmtRo(curr)}</div>
              {isSika ? (
                <div style={{ ...styles.tdNumRight, color: "var(--orange)" }}>
                  {fmtRo(ord)}
                </div>
              ) : (
                <>
                  <div style={{ ...styles.tdNumRight, color: "var(--orange)" }}>
                    {fmtRo(nel)}
                  </div>
                  <div style={{ ...styles.tdNumRight, color: "var(--orange)" }}>
                    {fmtRo(nef)}
                  </div>
                </>
              )}
              <div
                style={{
                  ...styles.tdNumRight,
                  fontWeight: 700,
                  color: colorForPct(realizat),
                }}
              >
                {fmtRo(ex)}
              </div>
              <div style={styles.tdPct}>
                <PctPill pct={realizat} />
              </div>
            </div>
            {isOpen && <StoresDrilldown stores={a.stores} variant={variant} />}
          </div>
        );
      })}
    </div>
  );
}

function StoresDrilldown({
  stores,
  variant,
}: {
  stores: { storeId: string | null; storeName: string; prevSales: string; currSales: string; nelivrate: string; nefacturate: string; ordersTotal: string; exercitiu: string }[];
  variant: TableVariant;
}) {
  const isSika = variant === "sika";
  const gridTpl = isSika
    ? "2fr 1fr 1fr 1fr 1.1fr 0.7fr"
    : "2fr 1fr 1fr 0.9fr 0.9fr 1.1fr 0.7fr";
  if (stores.length === 0) {
    return (
      <div style={styles.agentDetails}>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>Fără magazine.</span>
      </div>
    );
  }
  const headerCells = isSika
    ? ["MAGAZIN", "Luna ant.", "Curente", "Comenzi", "Exercițiu", "%"]
    : ["MAGAZIN", "Luna ant.", "Curente", "Nelivr.", "Nefact.", "Exercițiu", "%"];
  return (
    <div style={styles.storesDetails}>
      <div style={{ ...styles.storeHeaderRow, gridTemplateColumns: gridTpl }}>
        {headerCells.map((c, i) => (
          <div
            key={i}
            style={i === 0 ? undefined : { textAlign: "right" }}
          >
            {c}
          </div>
        ))}
      </div>
      {stores.map((s, i) => {
        const prev = toNum(s.prevSales);
        const curr = toNum(s.currSales);
        const nel = toNum(s.nelivrate);
        const nef = toNum(s.nefacturate);
        const ord = toNum(s.ordersTotal);
        const ex = toNum(s.exercitiu);
        const realizat = pctRealizat(ex, prev);
        return (
          <div
            key={s.storeId ?? `nomap-${i}`}
            style={{ ...styles.storeRow, gridTemplateColumns: gridTpl }}
          >
            <div style={styles.storeName} title={s.storeName}>
              {s.storeName}
            </div>
            <div style={styles.tdNumMuted}>{fmtRo(prev)}</div>
            <div style={styles.tdNumAccent}>{fmtRo(curr)}</div>
            {isSika ? (
              <div style={{ ...styles.tdNumRight, color: "var(--orange)" }}>{fmtRo(ord)}</div>
            ) : (
              <>
                <div style={{ ...styles.tdNumRight, color: "var(--orange)" }}>{fmtRo(nel)}</div>
                <div style={{ ...styles.tdNumRight, color: "var(--orange)" }}>{fmtRo(nef)}</div>
              </>
            )}
            <div
              style={{
                ...styles.tdNumRight,
                fontWeight: 700,
                color: colorForPct(realizat),
              }}
            >
              {fmtRo(ex)}
            </div>
            <div style={{ textAlign: "right" }}>
              <PctPill pct={realizat} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PctPill({ pct }: { pct: number }) {
  const c = colorForPct(pct);
  const bgAlpha =
    pct >= 100
      ? "rgba(52,211,153,0.15)"
      : pct >= 50
      ? "rgba(251,146,60,0.15)"
      : "rgba(239,68,68,0.15)";
  const icon = pct >= 100 ? "▲" : "▼";
  return (
    <span
      style={{
        ...styles.pctPill,
        background: bgAlpha,
        color: c,
      }}
    >
      {icon} {pct.toFixed(1)}%
    </span>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 10 },
  headerRow: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" },
  sectionHeader: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    marginTop: 6,
  },
  titleIcon: { fontSize: 18 },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: 0 },
  subTitle: { fontSize: 16, fontWeight: 700, color: "var(--cyan)", margin: 0 },
  periodLabel: { fontSize: 13, color: "var(--muted)" },
  lastUpdate: {
    fontSize: 11,
    color: "var(--muted)",
    marginLeft: "auto",
    fontStyle: "italic",
  },
  indBanner: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    padding: "8px 14px",
    background: "rgba(251,146,60,0.08)",
    border: "1px solid rgba(251,146,60,0.35)",
    borderRadius: 8,
    fontSize: 13,
  },
  indDivider: { color: "var(--muted)" },
  reportDateBanner: {
    padding: "8px 14px",
    background: "rgba(34,211,238,0.06)",
    border: "1px solid rgba(34,211,238,0.25)",
    borderRadius: 8,
    fontSize: 13,
    color: "var(--text)",
  },
  kpiRow: {
    display: "grid",
    gridAutoFlow: "column",
    gridAutoColumns: "minmax(0, 1fr)",
    gap: 12,
    width: "100%",
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
  kpiSub: { fontSize: 10.5, marginTop: 2, lineHeight: 1.2 },
  tableCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    overflow: "hidden",
  },
  agentHeaderRow: {
    display: "grid",
    gap: 14,
    padding: "4px 16px",
    borderBottom: "1px solid var(--border)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
  },
  thCenter: { textAlign: "center" },
  thRight: { textAlign: "right" },
  agentRow: {
    display: "grid",
    gap: 14,
    padding: "3px 16px",
    alignItems: "center",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
    cursor: "pointer",
  },
  agentTotalRow: {
    display: "grid",
    gap: 14,
    padding: "5px 16px",
    alignItems: "center",
    borderBottom: "2px solid var(--cyan)",
    background: "rgba(34,211,238,0.06)",
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
  tdNumMuted: { fontSize: 13, color: "var(--muted)", textAlign: "right" },
  tdNumAccent: { fontSize: 13, fontWeight: 600, color: "var(--cyan)", textAlign: "right" },
  tdNumRight: { fontSize: 13, textAlign: "right" },
  tdPct: { textAlign: "right" },
  totalLabel: {
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.08em",
    color: "var(--cyan)",
  },
  pctPill: {
    display: "inline-block",
    padding: "1px 7px",
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 700,
  },
  agentDetails: {
    padding: "4px 40px 6px",
    background: "rgba(0,0,0,0.2)",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
  },
  storesDetails: {
    padding: "2px 16px 4px 40px",
    background: "rgba(0,0,0,0.2)",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
  },
  storeHeaderRow: {
    display: "grid",
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
