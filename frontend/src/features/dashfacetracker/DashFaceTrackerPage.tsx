import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getFacingMonths, getRaionShare } from "./api";
import type {
  ParentRaionShare,
  RaionBrandShare,
  RaionShareAnalysis,
  RaionShareResponse,
  RaionShareScope,
  SubRaionShare,
} from "./types";

const OWN_BRAND_NAMES = new Set(["adeplast", "sika"]);

function scopeFromCompany(c: CompanyScope): RaionShareScope {
  if (c === "sika") return "sika";
  if (c === "sikadp") return "sikadp";
  return "adp";
}

function fmtRo(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

function fmtLuna(l: string): string {
  const [y, m] = l.split("-");
  const names = ["", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
    "Iul", "Aug", "Sep", "Oct", "Noi", "Dec"];
  return `${names[parseInt(m, 10)] ?? m} ${y}`;
}

function chipWhite(active: boolean, color: string): React.CSSProperties {
  return {
    background: active ? color : "#fff",
    color: active ? "#fff" : color,
    border: `1px solid ${active ? color : color + "66"}`,
    borderRadius: 5, cursor: "pointer",
  };
}

export default function DashFaceTrackerPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);

  const [months, setMonths] = useState<string[]>([]);
  const [luna, setLuna] = useState<string>("");
  const [data, setData] = useState<RaionShareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFacingMonths()
      .then((ms) => {
        if (cancelled) return;
        setMonths(ms);
        if (!luna && ms.length > 0) setLuna(ms[0]);
      })
      .catch(() => {});
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getRaionShare(apiScope, luna || undefined)
      .then((r) => { if (!cancelled) setData(r); })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiScope, luna]);

  const headerTitle = useMemo(() => {
    if (apiScope === "sikadp") return "Cotă de Raft — Adeplast & Sika";
    if (apiScope === "sika") return "Sika — Cotă de Raft per Sub-raion";
    return "Adeplast — Cotă de Raft per Sub-raion";
  }, [apiScope]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {headerTitle}
          {data?.luna ? ` · ${fmtLuna(data.luna)}` : ""}
        </h1>
      </div>

      {/* Luna chips */}
      {months.length > 0 && (
        <div data-chipgrid="true" style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
          gap: 5, marginBottom: 12,
        }}>
          {months.slice(0, 14).map((m) => (
            <button
              key={m} type="button" data-compact="true"
              onClick={() => setLuna(m)}
              style={chipWhite(luna === m, "#0ea5e9")}
              title={m}
            >
              {fmtLuna(m)}
            </button>
          ))}
        </div>
      )}

      {error && <div style={styles.error}>{error}</div>}
      {loading && !data && <div style={styles.loading}>Se încarcă…</div>}

      {(() => {
        const visible = data?.analyses.filter((a) => a.scope !== "sika") ?? [];
        if (!data) return null;
        if (!loading && visible.length === 0) {
          return (
            <div style={styles.empty}>
              Nu există date pentru luna {fmtLuna(data.luna)}.
            </div>
          );
        }
        return visible.map((a) => (
          <AnalysisSection key={a.scope} analysis={a} />
        ));
      })()}
    </div>
  );
}

function AnalysisSection({ analysis }: { analysis: RaionShareAnalysis }) {
  const accent = analysis.scope === "sika" ? "#22c55e" : "#3b82f6";
  const totalLabel = `${fmtRo(analysis.globalOwnFete)} / ${fmtRo(analysis.globalTotalFete)} fețe`;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        ...styles.analysisHeader,
        borderLeft: `4px solid ${accent}`,
      }}>
        <div>
          <h2 style={{ ...styles.analysisTitle, color: accent }}>
            {analysis.ownBrandName}
          </h2>
          <div style={styles.analysisSub}>
            vs {analysis.competitorNames.join(" · ")}
          </div>
        </div>
        <div style={styles.globalPill}>
          <span style={{ color: "var(--muted)" }}>Total</span>
          <strong style={{ color: "var(--text)" }}>{totalLabel}</strong>
          <span style={{
            color: analysis.globalOwnPct >= 30 ? "var(--green)" : "#d97706",
            fontWeight: 700,
          }}>
            {analysis.globalOwnPct.toFixed(1)}%
          </span>
        </div>
      </div>

      {analysis.parents.length === 0 ? (
        <div style={styles.empty}>Fără date pentru raioanele relevante.</div>
      ) : (
        analysis.parents.map((p) => (
          <ParentCard key={p.parentId} parent={p} ownName={analysis.ownBrandName} />
        ))
      )}
    </div>
  );
}

function ParentCard({ parent, ownName }: { parent: ParentRaionShare; ownName: string }) {
  return (
    <div style={styles.parentCard}>
      <div style={styles.parentHeader}>
        <h3 style={styles.parentTitle}>{parent.parentName}</h3>
        <div style={styles.parentStats}>
          <span style={{ color: "var(--muted)" }}>
            {fmtRo(parent.totalFete)} fețe
          </span>
          <span style={{
            color: parent.ownPct >= 30 ? "var(--green)" : "#d97706",
            fontWeight: 700,
          }}>
            {ownName}: {parent.ownPct.toFixed(1)}%
          </span>
        </div>
      </div>
      <div style={styles.subList}>
        {parent.subRaioane.map((s) => (
          <SubRaionRow key={s.raionId} sub={s} ownName={ownName} />
        ))}
      </div>
    </div>
  );
}

function SubRaionRow({ sub, ownName }: { sub: SubRaionShare; ownName: string }) {
  const empty = sub.totalFete === 0;
  const sortedBrands = [...sub.brands].sort((a, b) => b.pct - a.pct);
  const isMine = (b: RaionBrandShare) =>
    b.category === "own" || OWN_BRAND_NAMES.has(b.brandName.toLowerCase());
  return (
    <div style={styles.subRow}>
      <div style={styles.subHeader}>
        <span style={styles.subName}>{sub.raionName}</span>
        <span style={styles.subMeta}>
          {empty ? (
            <span style={{ color: "var(--muted)" }}>Fără date</span>
          ) : (
            <>
              <span style={{ color: "var(--muted)" }}>
                {fmtRo(sub.totalFete)} fețe
              </span>
              <span style={{
                color: sub.ownPct >= 30 ? "var(--green)" : "#d97706",
                fontWeight: 700,
              }}>
                {ownName}: {sub.ownPct.toFixed(1)}%
              </span>
            </>
          )}
        </span>
      </div>

      {!empty && (
        <div style={styles.pieRow}>
          <PiePanel
            label="Total"
            totalFete={sub.totalFete}
            ownPct={sub.ownPct}
            brands={sortedBrands}
            isMine={isMine}
            highlight
          />
          {sub.chains
            .filter((c) => c.totalFete > 0)
            .map((c) => {
              const sorted = [...c.brands].sort((a, b) => b.pct - a.pct);
              return (
                <PiePanel
                  key={c.chain}
                  label={c.chain}
                  totalFete={c.totalFete}
                  ownPct={c.ownPct}
                  brands={sorted}
                  isMine={isMine}
                />
              );
            })}
        </div>
      )}
    </div>
  );
}

function PiePanel({
  label, totalFete, ownPct, brands, isMine, highlight = false,
}: {
  label: string;
  totalFete: number;
  ownPct: number;
  brands: RaionBrandShare[];
  isMine: (b: RaionBrandShare) => boolean;
  highlight?: boolean;
}) {
  return (
    <div style={{
      ...styles.piePanel,
      background: highlight ? "var(--bg-elevated,#fafafa)" : "transparent",
      border: highlight ? "1px solid var(--border)" : "1px solid transparent",
    }}>
      <div style={styles.pieLabel} title={label}>{label}</div>
      <DonutChart brands={brands} size={76} />
      <div style={styles.pieMeta}>
        <span style={{ color: "var(--muted)" }}>{fmtRo(totalFete)} fețe</span>
        <span style={{
          color: ownPct >= 30 ? "var(--green)" : "#d97706",
          fontWeight: 700,
        }}>{ownPct.toFixed(1)}%</span>
      </div>
      <div style={styles.pieLegend}>
        {brands.map((b, i) => (
          <span key={`${b.brandId ?? "other"}-${i}`} style={styles.legendItem}>
            <span style={{
              width: 8, height: 8, borderRadius: 2,
              background: b.brandColor, display: "inline-block",
              opacity: b.category === "other" ? 0.55 : 1,
            }} />
            <span style={{
              fontWeight: isMine(b) ? 700 : 500,
              color: isMine(b) ? "var(--text)" : "var(--muted)",
            }}>{b.brandName}</span>
            <span style={{ color: "var(--muted)", fontVariantNumeric: "tabular-nums" }}>
              {b.pct.toFixed(1)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function DonutChart({ brands, size }: { brands: RaionBrandShare[]; size: number }) {
  const r = size / 2;
  const inner = r * 0.58;
  const segments = brands.filter((b) => b.pct > 0);
  let acc = 0;
  const arcs = segments.map((b) => {
    const start = acc;
    const end = acc + b.pct;
    acc = end;
    return { b, start, end };
  });

  const toXY = (pct: number, radius: number) => {
    const angle = (pct / 100) * 2 * Math.PI - Math.PI / 2;
    return [r + radius * Math.cos(angle), r + radius * Math.sin(angle)];
  };

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
      {arcs.length === 1 ? (
        <>
          <circle cx={r} cy={r} r={r} fill={arcs[0].b.brandColor}
            opacity={arcs[0].b.category === "other" ? 0.55 : 1} />
          <circle cx={r} cy={r} r={inner} fill="var(--card,#fff)" />
        </>
      ) : (
        arcs.map((a, i) => {
          const [x1, y1] = toXY(a.start, r);
          const [x2, y2] = toXY(a.end, r);
          const [x3, y3] = toXY(a.end, inner);
          const [x4, y4] = toXY(a.start, inner);
          const large = a.end - a.start > 50 ? 1 : 0;
          const d = [
            `M ${x1} ${y1}`,
            `A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`,
            `L ${x3} ${y3}`,
            `A ${inner} ${inner} 0 ${large} 0 ${x4} ${y4}`,
            "Z",
          ].join(" ");
          return (
            <path key={`${a.b.brandId ?? "other"}-${i}`} d={d}
              fill={a.b.brandColor}
              opacity={a.b.category === "other" ? 0.55 : a.b.category === "competitor" ? 0.9 : 1}>
              <title>{`${a.b.brandName}: ${fmtRo(a.b.totalFete)} fețe (${a.b.pct.toFixed(1)}%)`}</title>
            </path>
          );
        })
      )}
    </svg>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 20px", color: "var(--text)" },
  headerRow: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    gap: 12, marginBottom: 12, flexWrap: "wrap",
  },
  title: {
    margin: 0, fontSize: 17, fontWeight: 600, color: "var(--text)",
    letterSpacing: -0.2,
  },
  analysisHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    gap: 12, flexWrap: "wrap",
    padding: "10px 14px", marginBottom: 10,
    background: "var(--card)", borderRadius: "0 8px 8px 0",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  analysisTitle: { margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: -0.2 },
  analysisSub: { fontSize: 12, color: "var(--muted)", marginTop: 2 },
  globalPill: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "6px 12px", borderRadius: 20,
    background: "var(--bg-elevated,#fafafa)", border: "1px solid var(--border)",
    fontSize: 13,
  },
  error: {
    color: "var(--red)", padding: 12,
    background: "rgba(220, 38, 38, 0.08)", borderRadius: 6, marginBottom: 12,
  },
  loading: { color: "var(--muted)", padding: 12 },
  empty: {
    background: "var(--bg-elevated,#fafafa)",
    border: "1px solid var(--border)",
    borderRadius: 8, padding: 24,
    color: "var(--muted)", textAlign: "center",
  },
  parentCard: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: 14, marginBottom: 10,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  parentHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "baseline",
    marginBottom: 10, flexWrap: "wrap", gap: 8,
    paddingBottom: 8, borderBottom: "1px solid var(--border)",
  },
  parentTitle: { margin: 0, fontSize: 15, fontWeight: 700, color: "var(--text)" },
  parentStats: { display: "flex", alignItems: "center", gap: 10, fontSize: 12 },
  subList: { display: "flex", flexDirection: "column", gap: 12 },
  subRow: { display: "flex", flexDirection: "column", gap: 5 },
  subHeader: {
    display: "flex", justifyContent: "space-between", alignItems: "baseline",
    gap: 8, flexWrap: "wrap",
  },
  subName: { fontSize: 13, fontWeight: 600, color: "var(--text)" },
  subMeta: { display: "flex", alignItems: "center", gap: 8, fontSize: 12 },
  pieRow: {
    display: "flex", alignItems: "flex-start", gap: 10, marginTop: 4,
    flexWrap: "nowrap", overflowX: "auto",
  },
  piePanel: {
    display: "flex", flexDirection: "column", alignItems: "center",
    gap: 4, padding: "6px 8px", borderRadius: 6,
    flex: "1 1 0", minWidth: 0,
  },
  pieLabel: {
    fontSize: 11, fontWeight: 600, color: "var(--text)",
    maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  pieMeta: {
    display: "flex", gap: 6, fontSize: 10, alignItems: "baseline",
  },
  pieLegend: {
    display: "flex", flexDirection: "column", gap: 2,
    fontSize: 10, alignItems: "flex-start", width: "100%",
  },
  brandLegend: {
    display: "flex", flexDirection: "column", flexWrap: "wrap",
    gap: 4, fontSize: 11,
  },
  legendItem: { display: "inline-flex", alignItems: "center", gap: 4 },
};
