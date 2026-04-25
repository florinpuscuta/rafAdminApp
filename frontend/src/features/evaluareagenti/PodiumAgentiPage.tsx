import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { getCompensation, getDashboard } from "./api";
import { fmtRo, toNum } from "./shared";
import type { DashboardAgentRow, DashboardResponse } from "./types";

const MONTHS_SHORT = ["Ian", "Feb", "Mar", "Apr", "Mai", "Iun", "Iul", "Aug", "Sep", "Oct", "Noi", "Dec"];

type Weights = { eff: number; profit: number; growth: number; volume: number };

const DEFAULT_WEIGHTS: Weights = { eff: 30, profit: 25, growth: 25, volume: 20 };

interface Scored extends DashboardAgentRow {
  effScore: number;      // 0..100 — 100 − %cost, normalizat
  profitScore: number;   // 0..100 — (vanzari − cheltuieli), normalizat
  growthScore: number;   // 0..100 — YoY, normalizat
  volumeScore: number;   // 0..100 — vanzari/storeCount, normalizat
  vanzariPerStore: number;
  profitAbs: number;     // vanzari − cheltuieli (RON, brut)
  total: number;         // 0..100
}

/**
 * Podium Agenți — ranking compozit:
 *   Scor = w_eff·(100 − costPct) + w_growth·YoY_norm + w_volume·(vanzari/storeCount)_norm
 * Exclude agenți cu `bonus_vanzari_eligibil = false` sau vânzări = 0.
 */
export default function PodiumAgentiPage() {
  const now = new Date();
  const [year, setYear] = useState<number>(now.getFullYear());
  const [selectedMonths, setSelectedMonths] = useState<Set<number>>(() => new Set());
  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [ineligibleSet, setIneligibleSet] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const monthsArr = selectedMonths.size > 0
        ? Array.from(selectedMonths).sort((a, b) => a - b)
        : null;
      const [d, comp] = await Promise.all([
        getDashboard(year, monthsArr),
        getCompensation(),
      ]);
      setData(d);
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

  const eligibleRows = useMemo(() => {
    if (!data) return [];
    return data.rows;
  }, [data]);

  const scored: Scored[] = useMemo(() => {
    if (eligibleRows.length === 0) return [];

    const effVals = eligibleRows.map((r) => {
      const cp = r.costPct != null ? toNum(r.costPct) : 100;
      return Math.max(0, 100 - cp);
    });
    const profitVals = eligibleRows.map((r) => toNum(r.vanzari) - toNum(r.cheltuieli));
    const growthVals = eligibleRows.map((r) => r.yoyPct != null ? toNum(r.yoyPct) : 0);
    const volumeVals = eligibleRows.map((r) => {
      const v = toNum(r.vanzari);
      const sc = r.storeCount > 0 ? r.storeCount : 1;
      return v / sc;
    });

    const minMax = (arr: number[], x: number): number => {
      const mn = Math.min(...arr);
      const mx = Math.max(...arr);
      if (mx === mn) return 50;
      return ((x - mn) / (mx - mn)) * 100;
    };

    const wSum = weights.eff + weights.profit + weights.growth + weights.volume;
    const w = wSum > 0
      ? {
          eff: weights.eff / wSum,
          profit: weights.profit / wSum,
          growth: weights.growth / wSum,
          volume: weights.volume / wSum,
        }
      : { eff: 0.25, profit: 0.25, growth: 0.25, volume: 0.25 };

    return eligibleRows.map((r, i) => {
      const effScore = minMax(effVals, effVals[i]);
      const profitScore = minMax(profitVals, profitVals[i]);
      const growthScore = minMax(growthVals, growthVals[i]);
      const volumeScore = minMax(volumeVals, volumeVals[i]);
      const total =
        w.eff * effScore +
        w.profit * profitScore +
        w.growth * growthScore +
        w.volume * volumeScore;
      return {
        ...r,
        effScore,
        profitScore,
        growthScore,
        volumeScore,
        vanzariPerStore: volumeVals[i],
        profitAbs: profitVals[i],
        total,
      };
    }).sort((a, b) => b.total - a.total);
  }, [eligibleRows, weights]);

  const top3 = scored.slice(0, 3);
  const rest = scored.slice(3);

  return (
    <div className="agent-section" style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Podium Agenți</h1>
          <p style={styles.lead}>
            Ranking compozit care ține cont <strong>și de resursele folosite</strong>{" "}
            (cheltuieli + magazine alocate):
            {" "}<strong>Eficiență</strong> (100−%cost) ·{" "}
            <strong>Profit</strong> (vânzări−cheltuieli) ·{" "}
            <strong>Creștere</strong> (YoY) ·{" "}
            <strong>Productivitate</strong> (vânzări/magazin).
            Fiecare coloană e normalizată min-max între agenții eligibili,
            apoi combinată cu ponderile de mai jos.
          </p>
        </div>
        <div style={styles.controls}>
          <select
            data-wide="true"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            style={styles.select}
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
          <span style={styles.periodSep}>sau alege luni:</span>
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
                style={{
                  ...styles.monthCheckbox,
                  ...(checked ? styles.monthCheckboxActive : {}),
                }}
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

      <WeightsPanel weights={weights} setWeights={setWeights} />

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : scored.length === 0 ? (
        <div style={styles.muted}>
          Nu există agenți pentru perioada selectată.
        </div>
      ) : (
        <>
          <div style={styles.podium}>
            {top3.length >= 2 && <PodiumStep agent={top3[1]} place={2} />}
            {top3.length >= 1 && <PodiumStep agent={top3[0]} place={1} />}
            {top3.length >= 3 && <PodiumStep agent={top3[2]} place={3} />}
          </div>

          {rest.length > 0 && (
            <div style={styles.restWrap}>
              <h2 style={styles.restTitle}>Clasament complet</h2>
              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>#</th>
                      <th style={styles.thLeft}>Agent</th>
                      <th style={styles.th}>Scor</th>
                      <th style={styles.th}>Eficiență</th>
                      <th style={styles.th}>Profit</th>
                      <th style={styles.th}>Creștere</th>
                      <th style={styles.th}>Productiv.</th>
                      <th style={styles.thSep}>Mag.</th>
                      <th style={styles.th}>Vânzări</th>
                      <th style={styles.th}>Cheltuieli</th>
                      <th style={styles.th}>Profit (RON)</th>
                      <th style={styles.th}>% cost</th>
                      <th style={styles.th}>YoY</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scored.map((s, idx) => (
                      <tr key={s.agentId} style={idx < 3 ? styles.rowTop : undefined}>
                        <td style={styles.td}>
                          <RankBadge place={idx + 1} />
                        </td>
                        <td style={styles.tdLeft}>{s.agentName}</td>
                        <td style={{ ...styles.td, fontWeight: 700, color: "var(--cyan)" }}>
                          {fmtRo(s.total, 1)}
                        </td>
                        <td style={styles.td}>{fmtRo(s.effScore, 1)}</td>
                        <td style={styles.td}>{fmtRo(s.profitScore, 1)}</td>
                        <td style={styles.td}>{fmtRo(s.growthScore, 1)}</td>
                        <td style={styles.td}>{fmtRo(s.volumeScore, 1)}</td>
                        <td style={styles.tdSep}>{s.storeCount}</td>
                        <td style={styles.td}>{fmtRo(toNum(s.vanzari), 0)}</td>
                        <td style={styles.td}>{fmtRo(toNum(s.cheltuieli), 0)}</td>
                        <td
                          style={{
                            ...styles.td,
                            color: s.profitAbs >= 0 ? "#86efac" : "#fca5a5",
                            fontWeight: 600,
                          }}
                        >
                          {fmtRo(s.profitAbs, 0)}
                        </td>
                        <td style={styles.td}>
                          {s.costPct != null ? `${fmtRo(toNum(s.costPct), 2)}%` : "—"}
                        </td>
                        <td style={styles.td}>
                          {s.yoyPct != null
                            ? `${toNum(s.yoyPct) >= 0 ? "+" : ""}${fmtRo(toNum(s.yoyPct), 2)}%`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {ineligibleSet.size > 0 && (
            <p style={styles.footnote}>
              Agenți fără bonus de vânzări (incluși în ranking, marcați informativ):{" "}
              {data?.rows
                .filter((r) => ineligibleSet.has(r.agentId))
                .map((r) => r.agentName)
                .join(", ")}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function PodiumStep({ agent, place }: { agent: Scored; place: 1 | 2 | 3 }) {
  const config = {
    1: { height: 190, medal: "🥇", label: "Locul 1", color: "#fbbf24", bg: "linear-gradient(180deg, #fbbf24 0%, #d97706 100%)" },
    2: { height: 150, medal: "🥈", label: "Locul 2", color: "#cbd5e1", bg: "linear-gradient(180deg, #cbd5e1 0%, #64748b 100%)" },
    3: { height: 120, medal: "🥉", label: "Locul 3", color: "#f97316", bg: "linear-gradient(180deg, #f97316 0%, #9a3412 100%)" },
  }[place];

  return (
    <div style={styles.podiumCol}>
      <div style={styles.podiumCard}>
        <div style={styles.podiumMedal}>{config.medal}</div>
        <div style={styles.podiumName}>{agent.agentName}</div>
        <div style={{ ...styles.podiumScore, color: config.color }}>
          {fmtRo(agent.total, 1)} <span style={styles.podiumScoreUnit}>pct</span>
        </div>
        <div style={styles.podiumMetrics}>
          <div style={styles.podiumMetric}>
            <span style={styles.podiumMetricLabel}>% cost</span>
            <span style={styles.podiumMetricVal}>
              {agent.costPct != null ? `${fmtRo(toNum(agent.costPct), 1)}%` : "—"}
            </span>
          </div>
          <div style={styles.podiumMetric}>
            <span style={styles.podiumMetricLabel}>Profit</span>
            <span
              style={{
                ...styles.podiumMetricVal,
                color: agent.profitAbs >= 0 ? "#86efac" : "#fca5a5",
              }}
            >
              {fmtRo(agent.profitAbs, 0)}
            </span>
          </div>
          <div style={styles.podiumMetric}>
            <span style={styles.podiumMetricLabel}>YoY</span>
            <span
              style={{
                ...styles.podiumMetricVal,
                color: agent.yoyPct != null && toNum(agent.yoyPct) >= 0 ? "#86efac" : "#fca5a5",
              }}
            >
              {agent.yoyPct != null
                ? `${toNum(agent.yoyPct) >= 0 ? "+" : ""}${fmtRo(toNum(agent.yoyPct), 1)}%`
                : "—"}
            </span>
          </div>
        </div>
        <div style={styles.podiumResources}>
          <span style={styles.podiumResLabel}>Resurse</span>
          <span style={styles.podiumResVal}>
            {agent.storeCount} magazine · {fmtRo(toNum(agent.cheltuieli), 0)} RON cheltuieli
          </span>
        </div>
      </div>
      <div style={{ ...styles.podiumBase, height: config.height, background: config.bg }}>
        <span style={styles.podiumBaseLabel}>{config.label}</span>
      </div>
    </div>
  );
}

function RankBadge({ place }: { place: number }) {
  if (place === 1) return <span style={{ ...styles.rankBadge, background: "#fbbf24", color: "#000" }}>1</span>;
  if (place === 2) return <span style={{ ...styles.rankBadge, background: "#cbd5e1", color: "#000" }}>2</span>;
  if (place === 3) return <span style={{ ...styles.rankBadge, background: "#f97316", color: "#000" }}>3</span>;
  return <span style={styles.rankBadgeMuted}>{place}</span>;
}

function WeightsPanel({
  weights, setWeights,
}: { weights: Weights; setWeights: (w: Weights) => void }) {
  const update = (key: keyof Weights, v: number) => {
    setWeights({ ...weights, [key]: Math.max(0, Math.min(100, v)) });
  };
  const reset = () => setWeights(DEFAULT_WEIGHTS);
  return (
    <div style={styles.weightsPanel}>
      <span style={styles.periodLabelTxt}>Ponderi (%)</span>
      <WeightSlider label="Eficiență" value={weights.eff} onChange={(v) => update("eff", v)} />
      <WeightSlider label="Profit" value={weights.profit} onChange={(v) => update("profit", v)} />
      <WeightSlider label="Creștere" value={weights.growth} onChange={(v) => update("growth", v)} />
      <WeightSlider label="Productivitate" value={weights.volume} onChange={(v) => update("volume", v)} />
      <button onClick={reset} style={styles.clearBtn}>Reset (30/25/25/20)</button>
    </div>
  );
}

function WeightSlider({
  label, value, onChange,
}: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label style={styles.sliderWrap}>
      <span style={styles.sliderLabel}>{label}</span>
      <input
        type="range" min={0} max={100} step={5}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={styles.slider}
      />
      <span style={styles.sliderVal}>{value}</span>
    </label>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "12px 8px", width: "100%" },
  header: {
    display: "flex", justifyContent: "space-between", alignItems: "flex-start",
    gap: 16, marginBottom: 10, flexWrap: "wrap",
  },
  title: { fontSize: 18, fontWeight: 700, color: "var(--cyan)", margin: "0 0 2px" },
  lead: { color: "var(--muted)", fontSize: 11, margin: 0, maxWidth: 720, lineHeight: 1.5 },
  controls: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" },
  select: {
    padding: "4px 8px", fontSize: 12, background: "var(--bg-panel)",
    border: "1px solid var(--border)", color: "var(--text)", borderRadius: 4,
  },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: {
    padding: "6px 10px", background: "rgba(239,68,68,0.1)",
    border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5",
    borderRadius: 6, fontSize: 12, margin: "6px 0",
  },

  periodPanel: {
    padding: "8px 12px", background: "var(--bg-panel)",
    border: "1px solid var(--border)", borderRadius: 8, marginBottom: 10,
  },
  periodHead: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 8 },
  periodLabelTxt: {
    fontSize: 10, fontWeight: 700, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: "0.06em",
  },
  fullYearToggle: {
    display: "inline-flex", alignItems: "center", gap: 6,
    cursor: "pointer", padding: "3px 8px",
    border: "1px solid var(--border)", borderRadius: 4,
  },
  fullYearActive: { color: "var(--cyan)", fontWeight: 700, fontSize: 12 },
  fullYearIdle: { color: "var(--muted)", fontSize: 12 },
  periodSep: { color: "var(--muted)", fontSize: 11 },
  periodCurrent: { fontSize: 11, color: "var(--muted)" },
  periodCurrentVal: { color: "var(--text)" },
  checkbox: { width: 14, height: 14, accentColor: "var(--cyan)", cursor: "pointer" },
  clearBtn: {
    padding: "3px 8px", fontSize: 11, background: "transparent",
    border: "1px solid var(--border)", color: "var(--muted)",
    borderRadius: 4, cursor: "pointer",
  },
  monthsCheckboxGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(80px, 1fr))",
    gap: 4,
  },
  monthCheckbox: {
    display: "inline-flex", alignItems: "center", gap: 6,
    padding: "4px 8px", border: "1px solid var(--border)",
    borderRadius: 4, cursor: "pointer", fontSize: 12, color: "var(--muted)",
  },
  monthCheckboxActive: {
    borderColor: "var(--cyan)", background: "rgba(6,182,212,0.08)",
    color: "var(--text)", fontWeight: 600,
  },

  weightsPanel: {
    display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
    padding: "10px 14px", background: "var(--bg-panel)",
    border: "1px solid var(--border)", borderRadius: 8, marginBottom: 14,
  },
  sliderWrap: { display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12 },
  sliderLabel: { color: "var(--muted)", minWidth: 70 },
  slider: { width: 140, accentColor: "var(--cyan)" },
  sliderVal: {
    minWidth: 28, textAlign: "right", fontVariantNumeric: "tabular-nums",
    fontWeight: 600, color: "var(--text)",
  },

  podium: {
    display: "flex", justifyContent: "center", alignItems: "flex-end",
    gap: 16, padding: "24px 8px", marginBottom: 18, minHeight: 360,
  },
  podiumCol: {
    display: "flex", flexDirection: "column", alignItems: "center",
    flex: "1 1 200px", maxWidth: 260, minWidth: 170,
  },
  podiumCard: {
    width: "100%",
    padding: "14px 12px 16px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: "8px 8px 0 0",
    display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
    boxShadow: "0 -2px 8px rgba(0,0,0,0.15)",
  },
  podiumMedal: { fontSize: 32, lineHeight: 1 },
  podiumName: {
    fontSize: 14, fontWeight: 700, color: "var(--text)",
    textAlign: "center", minHeight: 34, lineHeight: 1.2,
  },
  podiumScore: { fontSize: 22, fontWeight: 800, fontVariantNumeric: "tabular-nums" },
  podiumScoreUnit: { fontSize: 11, color: "var(--muted)", fontWeight: 500 },
  podiumMetrics: {
    display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
    gap: 4, width: "100%", marginTop: 6,
    borderTop: "1px solid var(--border)", paddingTop: 8,
  },
  podiumMetric: {
    display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
  },
  podiumMetricLabel: {
    fontSize: 9, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: "0.04em",
  },
  podiumMetricVal: {
    fontSize: 12, fontWeight: 600, fontVariantNumeric: "tabular-nums",
  },
  podiumResources: {
    width: "100%", marginTop: 8, paddingTop: 8,
    borderTop: "1px dashed var(--border)",
    display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
  },
  podiumResLabel: {
    fontSize: 9, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: "0.06em",
  },
  podiumResVal: {
    fontSize: 11, color: "var(--text)", fontVariantNumeric: "tabular-nums",
    textAlign: "center",
  },
  podiumBase: {
    width: "100%",
    display: "flex", alignItems: "center", justifyContent: "center",
    color: "#000", fontWeight: 800, fontSize: 14,
    letterSpacing: "0.08em", textTransform: "uppercase",
    borderRadius: "0 0 6px 6px",
  },
  podiumBaseLabel: { textShadow: "0 1px 2px rgba(255,255,255,0.25)" },

  restWrap: { marginTop: 8 },
  restTitle: {
    fontSize: 13, fontWeight: 700, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: "0.08em",
    margin: "0 0 8px",
  },
  tableWrap: {
    background: "var(--bg-panel)", border: "1px solid var(--border)",
    borderRadius: 8, overflow: "hidden",
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: {
    padding: "8px 6px", textAlign: "right",
    fontSize: 10, fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)",
    whiteSpace: "nowrap",
  },
  thLeft: {
    padding: "8px 10px", textAlign: "left",
    fontSize: 10, fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)",
    whiteSpace: "nowrap",
  },
  td: {
    padding: "6px 8px", textAlign: "right",
    borderBottom: "1px solid var(--border)",
    fontVariantNumeric: "tabular-nums",
  },
  thSep: {
    padding: "8px 6px", textAlign: "right",
    fontSize: 10, fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    borderLeft: "2px solid var(--border)",
    background: "var(--bg-sidebar)", whiteSpace: "nowrap",
  },
  tdSep: {
    padding: "6px 8px", textAlign: "right",
    borderBottom: "1px solid var(--border)",
    borderLeft: "2px solid var(--border)",
    fontVariantNumeric: "tabular-nums",
  },
  tdLeft: {
    padding: "6px 10px", textAlign: "left",
    borderBottom: "1px solid var(--border)",
  },
  rowTop: { background: "rgba(6,182,212,0.04)" },
  rankBadge: {
    display: "inline-block", width: 22, height: 22, lineHeight: "22px",
    textAlign: "center", borderRadius: "50%", fontSize: 11, fontWeight: 800,
  },
  rankBadgeMuted: {
    display: "inline-block", width: 22, height: 22, lineHeight: "22px",
    textAlign: "center", borderRadius: "50%", fontSize: 11,
    color: "var(--muted)", background: "var(--bg-sidebar)",
  },
  footnote: {
    marginTop: 12, padding: "6px 10px", fontSize: 11, color: "var(--muted)",
    fontStyle: "italic",
  },
};
