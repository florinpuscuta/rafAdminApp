/**
 * Facing Tracker — port al `renderFacingTracker` (legacy templates/index.html:14836).
 *
 * 4 tab-uri (identice cu legacy):
 *   1. Dashboard       — KPI per rețea + matrice per magazin
 *   2. Introducere     — grilă magazin × raioane × branduri (input per lună)
 *   3. Evoluție        — tabel multi-lună
 *   4. Configurare     — CRUD raioane + branduri + matrice chain×brand
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { useConfirm } from "../../shared/ui/ConfirmDialog";
import {
  addBrand,
  addRaion,
  deleteBrand,
  deleteRaion,
  getConfig,
  getDashboard,
  getEvolution,
  getMonths,
  getSnapshots,
  getStores,
  migrateMonth,
  saveChainBrands,
  saveSnapshots,
  updateBrand,
  updateRaion,
} from "./api";
import type {
  Brand,
  ConfigResponse,
  DashboardResponse,
  EvolutionResponse,
  Raion,
  SaveEntry,
  Snapshot,
  UUID,
} from "./types";

type TabId = "dashboard" | "input" | "evolution" | "config";

const MONTH_LABELS = [
  "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function lunaLabel(l: string | null | undefined): string {
  if (!l) return "-";
  const parts = l.split("-");
  if (parts.length < 2) return l;
  const m = parseInt(parts[1], 10);
  return `${MONTH_LABELS[m] || parts[1]} ${parts[0]}`;
}

function fmtNum(n: number | null | undefined): string {
  if (n == null) return "0";
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 1 }).format(n);
}

function extractChain(storeName: string): string {
  if (!storeName) return "Alte";
  const u = storeName.toUpperCase();
  if (u.includes("DEDEMAN")) return "Dedeman";
  if (u.includes("ALTEX")) return "Altex";
  if (u.includes("LEROY")) return "Leroy Merlin";
  if (u.includes("HORNBACH")) return "Hornbach";
  return "Alte";
}

function currentLuna(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function MktFacingPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [tab, setTab] = useState<TabId>("dashboard");
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [stores, setStores] = useState<string[]>([]);
  const [months, setMonths] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const curLuna = useMemo(currentLuna, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, st, mn] = await Promise.all([getConfig(), getStores(), getMonths()]);
      setConfig(cfg);
      setStores(st.stores || []);
      setMonths(mn.months || []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  if (loading && !config) {
    return <div style={styles.loading}>Se încarcă Facing Tracker…</div>;
  }
  if (error) {
    return <div style={styles.error}>{error}</div>;
  }
  if (!config) return null;

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>📏 Facing Tracker — Cote de Raft</h1>

      <div style={styles.tabBar}>
        <TabButton active={tab === "dashboard"} onClick={() => setTab("dashboard")}>
          📊 Dashboard
        </TabButton>
        <TabButton active={tab === "input"} onClick={() => setTab("input")}>
          ✏️ Introducere Date
        </TabButton>
        <TabButton active={tab === "evolution"} onClick={() => setTab("evolution")}>
          📈 Evoluție
        </TabButton>
        <TabButton active={tab === "config"} onClick={() => setTab("config")}>
          ⚙️ Configurare
        </TabButton>
      </div>

      {tab === "dashboard" && (
        <DashboardTab curLuna={curLuna} months={months} config={config} />
      )}
      {tab === "input" && (
        <InputTab
          stores={stores}
          months={months}
          curLuna={curLuna}
          config={config}
          onSaved={async () => {
            const mn = await getMonths();
            setMonths(mn.months || []);
            toast.success("Salvat");
          }}
        />
      )}
      {tab === "evolution" && (
        <EvolutionTab stores={stores} config={config} />
      )}
      {tab === "config" && (
        <ConfigTab
          config={config}
          reload={loadAll}
          onEdit={() => toast.success("Actualizat")}
          onDelete={async () => toast.success("Șters")}
          confirm={confirm}
        />
      )}
    </div>
  );
}

// ── Dashboard tab ───────────────────────────────────────────────────────────

function DashboardTab({ curLuna, months, config }: {
  curLuna: string; months: string[]; config: ConfigResponse;
}) {
  const [luna, setLuna] = useState(curLuna);
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getDashboard(luna)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Eroare"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [luna]);

  const allMonths = useMemo(() => {
    const s = new Set<string>([curLuna, ...months]);
    return Array.from(s).sort().reverse();
  }, [curLuna, months]);

  if (loading) return <div style={styles.loading}>Se încarcă dashboard…</div>;
  if (error) return <div style={styles.error}>{error}</div>;
  if (!data || !data.chains.length) {
    return (
      <div>
        <LunaSelector luna={luna} setLuna={setLuna} months={allMonths} />
        <div style={styles.empty}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📏</div>
          <p>Nu există date pentru această lună.<br/>Adaugă date din tab-ul <b>Introducere Date</b>.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <LunaSelector luna={luna} setLuna={setLuna} months={allMonths} />

      <div style={styles.globalBanner}>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "baseline" }}>
          <div>
            <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 2 }}>
              Cotă DIY globală
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontSize: 24, fontWeight: 700, color: "var(--green)", letterSpacing: -0.4 }}>
                {fmtNum(data.globalOwnPctWeighted)}%
              </span>
              <span style={styles.deltaLabel(data.globalOwnPctDelta)}>
                {data.globalOwnPctDelta > 0 ? "▲" : data.globalOwnPctDelta < 0 ? "▼" : "–"}{fmtNum(Math.abs(data.globalOwnPctDelta))}pp
              </span>
            </div>
          </div>
          <div style={{ borderLeft: "1px solid var(--border)", paddingLeft: 20 }}>
            <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 2 }}>
              Aritmetic
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontSize: 20, fontWeight: 600, color: "var(--text)" }}>
                {fmtNum(data.globalOwnPctArith)}%
              </span>
              <span style={styles.deltaLabel(data.globalOwnPctArithDelta)}>
                {data.globalOwnPctArithDelta > 0 ? "▲" : data.globalOwnPctArithDelta < 0 ? "▼" : "–"}{fmtNum(Math.abs(data.globalOwnPctArithDelta))}pp
              </span>
            </div>
          </div>
          <div style={{ marginLeft: "auto", fontSize: 11, color: "var(--muted)", textAlign: "right" }}>
            <div><b style={{ color: "var(--text)" }}>{data.totalMagazine}</b> magazine · <b style={{ color: "var(--text)" }}>{data.globalTotalFete}</b> fețe</div>
            <div>{data.globalOwnTotalFete} fețe proprii</div>
          </div>
        </div>

        {data.globalCompetitors.length > 0 && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)", display: "flex", gap: 14, flexWrap: "wrap" }}>
            {data.globalCompetitors.map((c) => (
              <div key={c.brandId} style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ display: "inline-block", width: 8, height: 8, background: c.brandColor, borderRadius: 2 }} />
                <span style={{ color: "var(--muted)" }}>{c.brandName}</span>
                <b style={{ color: "var(--text)" }}>{fmtNum(c.pct)}%</b>
                <span style={{ ...styles.deltaInline(c.deltaPp), fontSize: 10 }}>{c.deltaPp > 0 ? "+" : ""}{fmtNum(c.deltaPp)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {data.chains.map((ch) => (
        <ChainCard key={ch.chain} chain={ch} config={config} />
      ))}
    </div>
  );
}

function ChainCard({ chain, config }: {
  chain: DashboardResponse["chains"][0]; config: ConfigResponse;
}) {
  const [open, setOpen] = useState(false);
  const ownDeltaColor = chain.ownPctDelta > 0 ? "var(--green)" : chain.ownPctDelta < 0 ? "var(--red)" : "var(--muted)";
  return (
    <div style={{ ...styles.card, padding: 0, overflow: "hidden" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap",
        padding: "14px 18px", cursor: "pointer",
        borderBottom: "1px solid var(--border)",
      }} onClick={() => setOpen(!open)}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flex: "0 0 auto" }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>{open ? "▾" : "▸"}</span>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, letterSpacing: -0.2 }}>{chain.chain}</h3>
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{
            fontSize: 28, fontWeight: 700, letterSpacing: -0.6,
            color: "var(--green)", fontVariantNumeric: "tabular-nums",
            lineHeight: 1,
          }}>{fmtNum(chain.ownPctWeighted)}%</span>
          <span style={{
            fontSize: 11, fontWeight: 600, color: ownDeltaColor,
            fontVariantNumeric: "tabular-nums",
          }}>
            {chain.ownPctDelta > 0 ? "▲" : chain.ownPctDelta < 0 ? "▼" : "–"}{fmtNum(Math.abs(chain.ownPctDelta))}pp
          </span>
        </div>

        <div style={{ marginLeft: "auto", textAlign: "right", fontSize: 11, color: "var(--muted)" }}>
          <b style={{ color: "var(--text)" }}>{chain.nrMagazine}</b> magazine · {chain.totalFeteAll} fețe
        </div>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
        gap: 1, background: "var(--border)",
      }}>
        {chain.brandsSummary.map((b) => {
          const deltaColor = b.deltaAvg > 0 ? "var(--green)" : b.deltaAvg < 0 ? "var(--red)" : "var(--muted)";
          return (
            <div key={b.brandId} style={{
              padding: "10px 12px", background: "var(--card)",
              borderTop: `2px solid ${b.brandColor}`,
              display: "flex", flexDirection: "column", gap: 2,
            }}>
              <div style={{
                fontSize: 10, fontWeight: 600, color: b.brandColor,
                textTransform: "uppercase", letterSpacing: 0.5,
              }}>{b.brandName}</div>
              <div style={{
                fontSize: 22, fontWeight: 700, letterSpacing: -0.5,
                color: "var(--text)", fontVariantNumeric: "tabular-nums",
                lineHeight: 1.1,
              }}>{fmtNum(b.pct)}%</div>
              <div style={{ fontSize: 10, color: "var(--muted)", display: "flex", justifyContent: "space-between" }}>
                <span>{fmtNum(b.avgFete)}/mag</span>
                <span style={{ color: deltaColor, fontWeight: 600 }}>
                  {b.deltaAvg > 0 ? "+" : ""}{fmtNum(b.deltaAvg)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Compoziție pe grupuri (bar stacked + legendă) — port legacy:15562 */}
      <GroupComposition chain={chain} config={config} />

      {/* Matrice Sub-raion × Brand (P/A) — identic cu legacy renderFacing */}
      <SubRaionMatrix chain={chain} config={config} />

      {open && (
        <div style={{ borderTop: "1px solid var(--border)" }}>
          <StoresDetailTable chain={chain} />
        </div>
      )}
    </div>
  );
}

/**
 * Calculează P (ponderat) + A (aritmetic) per (sub-raion, brand) pentru o rețea.
 * Algoritm port 1:1 din legacy JS (templates/index.html:15626-15688).
 */
function SubRaionMatrix({
  chain, config,
}: {
  chain: DashboardResponse["chains"][0];
  config: ConfigResponse;
}) {
  const { leafRaioane, brandCols, rows, groupColors } = useMemo(() => {
    const groups = config.raioane.filter((r) => !r.parentId)
      .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
    const kidsOf: Record<string, Raion[]> = {};
    for (const r of config.raioane) {
      if (r.parentId) (kidsOf[r.parentId] ||= []).push(r);
    }
    Object.values(kidsOf).forEach((arr) => arr.sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)));

    // Aceeași paletă deterministă ca GroupComposition (legacy `groupPalette`).
    const palette = ["#06b6d4", "#f59e0b", "#8b5cf6", "#ec4899", "#22c55e", "#3b82f6"];
    const colors: Record<string, string> = {};
    groups.forEach((g, idx) => { colors[g.name] = palette[idx % palette.length]; });

    type Leaf = { name: string; isGroup: boolean; groupName: string };
    const leafs: Leaf[] = [];
    for (const g of groups) {
      const kids = kidsOf[g.id] || [];
      if (kids.length === 0) {
        leafs.push({ name: g.name, isGroup: true, groupName: g.name });
      } else {
        for (const c of kids) {
          leafs.push({ name: c.name, isGroup: false, groupName: g.name });
        }
      }
    }

    // Branduri relevante pentru rețea (din chainBrands matrix).
    const allowedIds = new Set(config.chainBrands[chain.chain] || []);
    const brandList = allowedIds.size > 0
      ? config.brands.filter((b) => allowedIds.has(b.id))
      : config.brands.slice();
    brandList.sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));

    // storeAgg[storeName][raionName][brandId] = nrFete
    type Agg = Record<string, Record<string, Record<string, number>>>;
    const storeAgg: Agg = {};
    const allowedNames = new Set(brandList.map((b) => b.name));

    for (const [sn, st] of Object.entries(chain.stores)) {
      storeAgg[sn] = {};
      for (const [rn, items] of Object.entries(st.raioane)) {
        storeAgg[sn][rn] = {};
        for (const it of items) {
          if (!allowedNames.has(it.brandName)) continue;
          const brand = brandList.find((b) => b.name === it.brandName);
          if (!brand) continue;
          storeAgg[sn][rn][brand.id] =
            (storeAgg[sn][rn][brand.id] || 0) + (it.nrFete || 0);
        }
      }
    }

    // Pentru fiecare (leaf, brand) calculăm P + A
    type Row = {
      leaf: Leaf;
      brandPA: Record<string, { P: number | null; A: number | null }>;
      anyData: boolean;
    };
    const rowsOut: Row[] = [];
    for (const lr of leafs) {
      const brandPA: Row["brandPA"] = {};
      let anyData = false;
      for (const b of brandList) {
        let sumBrand = 0;
        let sumTotal = 0;
        const pctList: number[] = [];
        for (const sn of Object.keys(storeAgg)) {
          const rd = storeAgg[sn][lr.name];
          if (!rd) continue;
          const storeTotal = Object.values(rd).reduce((s, v) => s + v, 0);
          const storeBrand = rd[b.id] || 0;
          if (storeTotal === 0) continue;
          sumBrand += storeBrand;
          sumTotal += storeTotal;
          pctList.push((storeBrand / storeTotal) * 100);
        }
        const P = sumTotal > 0 ? (sumBrand / sumTotal) * 100 : null;
        const A = pctList.length > 0
          ? pctList.reduce((s, v) => s + v, 0) / pctList.length
          : null;
        brandPA[b.id] = { P, A };
        if (P != null) anyData = true;
      }
      rowsOut.push({ leaf: lr, brandPA, anyData });
    }

    return { leafRaioane: leafs, brandCols: brandList, rows: rowsOut, groupColors: colors };
  }, [chain, config]);

  const anyData = rows.some((r) => r.anyData);
  if (!anyData || leafRaioane.length === 0) return null;

  return (
    <div style={{
      margin: "0 16px 16px", padding: 14,
      background: "var(--bg-elevated)",
      border: "1px solid var(--border)",
      borderRadius: 8,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: "var(--muted)" }}>
          Cota de raft per sub-raion — <b style={{ color: "var(--text)" }}>{chain.chain}</b>
        </div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          <b style={{ color: "var(--text)" }}>P</b> = ponderat (Σfețe brand / Σfețe total) ·{" "}
          <b style={{ color: "var(--text)" }}>A</b> = aritmetic (media %-elor per magazin)
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ ...styles.table, fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ ...styles.th, minWidth: 180, textAlign: "left" }}>Sub-raion</th>
              {brandCols.map((b) => (
                <th key={b.id} colSpan={2} style={{
                  ...styles.th, textAlign: "center", color: b.color,
                  borderBottom: `2px solid ${b.color}55`,
                  minWidth: 100,
                }}>
                  {b.name}
                </th>
              ))}
            </tr>
            <tr>
              <th style={{ ...styles.th, textAlign: "left", fontSize: 10 }}></th>
              {brandCols.map((b) => (
                <>
                  <th key={`${b.id}-P`} style={{ ...styles.th, textAlign: "center", fontSize: 10, width: 50 }}>P</th>
                  <th key={`${b.id}-A`} style={{ ...styles.th, textAlign: "center", fontSize: 10, width: 50 }}>A</th>
                </>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.filter((r) => r.anyData).map((r) => {
              const lr = r.leaf;
              return (
                <tr key={lr.name} style={{
                  background: lr.isGroup ? "rgba(8,145,178,0.04)" : "rgba(148,163,184,0.02)",
                }}>
                  <td style={{
                    ...styles.td, paddingLeft: lr.isGroup ? 12 : 14,
                  }}>
                    {lr.isGroup ? (
                      <span>
                        <span style={{ color: groupColors[lr.groupName], marginRight: 6 }}>↳</span>
                        <b style={{ color: "var(--text)", fontSize: 13 }}>{lr.name}</b>{" "}
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>({lr.groupName})</span>
                      </span>
                    ) : (
                      <span>
                        <span style={{ color: groupColors[lr.groupName], marginRight: 6 }}>↳</span>
                        <b style={{ color: "var(--text)", fontSize: 13 }}>{lr.name}</b>{" "}
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>({lr.groupName})</span>
                      </span>
                    )}
                  </td>
                  {brandCols.map((b) => {
                    const pa = r.brandPA[b.id];
                    if (!pa || pa.P == null) {
                      return (
                        <>
                          <td key={`${b.id}-P-${lr.name}`} style={{ ...styles.td, textAlign: "center", color: "var(--muted)", opacity: 0.3 }}>—</td>
                          <td key={`${b.id}-A-${lr.name}`} style={{ ...styles.td, textAlign: "center", color: "var(--muted)", opacity: 0.3 }}>—</td>
                        </>
                      );
                    }
                    const pShade = Math.min(0.25, 0.05 + pa.P / 400);
                    const aShade = pa.A != null ? Math.min(0.25, 0.05 + pa.A / 400) : 0;
                    const toHex = (s: number) => Math.floor(s * 255).toString(16).padStart(2, "0");
                    return (
                      <>
                        <td key={`${b.id}-P-${lr.name}`} style={{
                          ...styles.td, textAlign: "center",
                          background: `${b.color}${toHex(pShade)}`,
                          color: b.color, fontWeight: 700,
                        }}>{pa.P.toFixed(1)}%</td>
                        <td key={`${b.id}-A-${lr.name}`} style={{
                          ...styles.td, textAlign: "center",
                          background: pa.A != null ? `${b.color}${toHex(aShade)}` : "transparent",
                          color: pa.A != null ? b.color : "var(--muted)",
                          opacity: pa.A != null ? 0.85 : 0.3,
                        }}>{pa.A != null ? `${pa.A.toFixed(1)}%` : "—"}</td>
                      </>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 8, fontStyle: "italic" }}>
        💡 Dacă P ≠ A: magazinele au compoziții diferite și brand-ul e mai bine reprezentat în magazine mari (P &gt; A) sau mici (P &lt; A).
      </div>
    </div>
  );
}

/**
 * Compoziție pe grupuri (Construcții/Adezivi/Chimice) pentru toată rețeaua.
 * Bar orizontal stacked + legendă cu sub-compoziție per sub-raion.
 * Port 1:1 din legacy templates/index.html:15562-15624.
 */
function GroupComposition({
  chain, config,
}: {
  chain: DashboardResponse["chains"][0];
  config: ConfigResponse;
}) {
  const { groupTotals, grandTotal, groupColors, groups } = useMemo(() => {
    const grps = config.raioane.filter((r) => !r.parentId)
      .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
    const kidsOf: Record<string, Raion[]> = {};
    for (const r of config.raioane) {
      if (r.parentId) (kidsOf[r.parentId] ||= []).push(r);
    }

    const allowedIds = new Set(config.chainBrands[chain.chain] || []);
    const allowedNames = new Set(
      (allowedIds.size > 0
        ? config.brands.filter((b) => allowedIds.has(b.id))
        : config.brands
      ).map((b) => b.name)
    );

    type GT = { total: number; children: Record<string, number> };
    const totals: Record<string, GT> = {};
    for (const g of grps) totals[g.name] = { total: 0, children: {} };

    for (const st of Object.values(chain.stores)) {
      for (const g of grps) {
        // Date legacy direct pe grup
        for (const it of (st.raioane[g.name] || [])) {
          if (allowedNames.has(it.brandName)) {
            totals[g.name].total += it.nrFete || 0;
          }
        }
        // Date pe sub-raioane
        for (const c of (kidsOf[g.id] || [])) {
          for (const it of (st.raioane[c.name] || [])) {
            if (allowedNames.has(it.brandName)) {
              const v = it.nrFete || 0;
              totals[g.name].total += v;
              totals[g.name].children[c.name] =
                (totals[g.name].children[c.name] || 0) + v;
            }
          }
        }
      }
    }

    const grand = Object.values(totals).reduce((s, g) => s + g.total, 0);
    const palette = ["#06b6d4", "#f59e0b", "#8b5cf6", "#ec4899", "#22c55e", "#3b82f6"];
    const colors: Record<string, string> = {};
    grps.forEach((g, idx) => { colors[g.name] = palette[idx % palette.length]; });

    return { groupTotals: totals, grandTotal: grand, groupColors: colors, groups: grps };
  }, [chain, config]);

  if (grandTotal === 0) return null;

  return (
    <div style={{
      margin: "0 16px 12px", padding: 12,
      background: "var(--bg-elevated)",
      border: "1px solid var(--border)",
      borderRadius: 8,
    }}>
      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 8 }}>
        Compoziție pe grupuri — <b style={{ color: "var(--text)" }}>{chain.chain}</b>{" "}
        ({grandTotal} fețe totale relevante)
      </div>

      {/* Bar principal stacked */}
      <div style={{
        display: "flex", height: 22, borderRadius: 6,
        overflow: "hidden", marginBottom: 8,
      }}>
        {groups.map((g) => {
          const gt = groupTotals[g.name];
          if (!gt || gt.total === 0) return null;
          const pct = (gt.total / grandTotal) * 100;
          return (
            <div key={g.name} style={{
              width: `${pct}%`, background: groupColors[g.name],
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontSize: 11, fontWeight: 700,
            }} title={`${g.name}: ${gt.total} fețe (${pct.toFixed(1)}%)`}>
              {pct >= 8 ? `${g.name} ${pct.toFixed(0)}%` : ""}
            </div>
          );
        })}
      </div>

      {/* Legendă + sub-compoziție */}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 11 }}>
        {groups.map((g) => {
          const gt = groupTotals[g.name];
          if (!gt || gt.total === 0) return null;
          const pct = (gt.total / grandTotal) * 100;
          const kidsEntries = Object.entries(gt.children).filter(([, v]) => v > 0);
          let subCompo = "";
          if (kidsEntries.length > 0) {
            const kidsTotal = kidsEntries.reduce((s, [, v]) => s + v, 0);
            subCompo = " · " + kidsEntries.map(([n, v]) =>
              `${n} ${(v / kidsTotal * 100).toFixed(0)}%`
            ).join(", ");
          }
          return (
            <div key={g.name}>
              <span style={{ color: groupColors[g.name] }}>●</span>{" "}
              <b style={{ color: "var(--text)" }}>{g.name}</b>: {gt.total} ({pct.toFixed(1)}%)
              {subCompo && <span style={{ color: "var(--muted)" }}>{subCompo}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StoresDetailTable({ chain }: { chain: DashboardResponse["chains"][0] }) {
  return (
    <div style={{ padding: "0 12px 12px" }}>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>
        Detaliu pe magazine ({Object.keys(chain.stores).length})
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Magazin / Raion</th>
            <th style={styles.th}>Detalii</th>
          </tr>
        </thead>
        <tbody>
          {Object.values(chain.stores).map((s) => (
            <tr key={s.storeName}>
              <td style={styles.td}>{s.storeName}</td>
              <td style={styles.td}>
                {Object.entries(s.raioane).map(([rn, items]) => (
                  <div key={rn} style={{ marginBottom: 4, fontSize: 12 }}>
                    <b>{rn}:</b>{" "}
                    {items.map((it, i) => (
                      <span key={i} style={{ marginRight: 8 }}>
                        <span style={{ color: it.brandColor }}>●</span> {it.brandName}: {it.nrFete}
                      </span>
                    ))}
                  </div>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LunaSelector({ luna, setLuna, months }: {
  luna: string; setLuna: (l: string) => void; months: string[];
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ color: "var(--muted)", marginRight: 8 }}>Luna:</label>
      <select value={luna} onChange={(e) => setLuna(e.target.value)} style={styles.select}>
        {months.map((m) => (
          <option key={m} value={m}>{lunaLabel(m)}</option>
        ))}
      </select>
    </div>
  );
}

// ── Input tab ───────────────────────────────────────────────────────────────

function InputTab({
  stores, months, curLuna, config, onSaved,
}: {
  stores: string[]; months: string[]; curLuna: string;
  config: ConfigResponse; onSaved: () => void;
}) {
  const [store, setStore] = useState("");
  const [luna, setLuna] = useState(curLuna);
  const [snaps, setSnaps] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [hasParentLegacy, setHasParentLegacy] = useState(false);
  const toast = useToast();

  const allMonths = useMemo(() => {
    const s = new Set<string>([curLuna, ...months]);
    return Array.from(s).sort().reverse();
  }, [curLuna, months]);

  const chain = useMemo(() => extractChain(store), [store]);
  const relevantBrands = useMemo((): Brand[] => {
    const ids = config.chainBrands[chain];
    if (!ids || !ids.length) return config.brands;
    const s = new Set(ids);
    return config.brands.filter((b) => s.has(b.id));
  }, [config, chain]);

  const { groups, childrenOf } = useMemo(() => {
    const g = config.raioane.filter((r) => !r.parentId)
      .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
    const c: Record<string, Raion[]> = {};
    for (const r of config.raioane) {
      if (r.parentId) {
        (c[r.parentId] ||= []).push(r);
      }
    }
    Object.values(c).forEach((arr) => arr.sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)));
    return { groups: g, childrenOf: c };
  }, [config]);

  useEffect(() => {
    if (!store) return;
    getSnapshots(store, luna).then((r) => {
      const map: Record<string, number> = {};
      let parentFlag = false;
      (r.data || []).forEach((s: Snapshot) => {
        map[`${s.raionId}_${s.brandId}`] = s.nrFete;
        const raion = config.raioane.find((x) => x.id === s.raionId);
        if (raion && !raion.parentId && (childrenOf[raion.id] || []).length > 0 && (s.nrFete || 0) > 0) {
          parentFlag = true;
        }
      });
      setSnaps(map);
      setHasParentLegacy(parentFlag);
    });
  }, [store, luna, config.raioane, childrenOf]);

  const handleChange = (raionId: UUID, brandId: UUID, v: string) => {
    setSnaps((prev) => ({ ...prev, [`${raionId}_${brandId}`]: parseInt(v) || 0 }));
  };

  const groupTotal = (groupId: UUID, brandId: UUID): number => {
    const kids = childrenOf[groupId] || [];
    return kids.reduce((sum, k) => sum + (snaps[`${k.id}_${brandId}`] || 0), 0);
  };

  const handleSave = async () => {
    if (!store) return;
    const entries: SaveEntry[] = [];
    for (const g of groups) {
      const kids = childrenOf[g.id] || [];
      if (!kids.length) {
        for (const b of relevantBrands) {
          entries.push({
            storeName: store, raionId: g.id, brandId: b.id, luna,
            nrFete: snaps[`${g.id}_${b.id}`] || 0,
          });
        }
      } else {
        for (const k of kids) {
          for (const b of relevantBrands) {
            entries.push({
              storeName: store, raionId: k.id, brandId: b.id, luna,
              nrFete: snaps[`${k.id}_${b.id}`] || 0,
            });
          }
        }
      }
    }
    setSaving(true);
    try {
      const res = await saveSnapshots(entries);
      toast.success(`Salvat ${res.saved} înregistrări`);
      onSaved();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare la salvare");
    } finally {
      setSaving(false);
    }
  };

  const handleMigrate = async () => {
    if (!window.confirm(`Confirmi migrarea datelor de pe Construcții/Adezivi/Chimice în sub-raioanele default pentru ${lunaLabel(luna)}?`)) return;
    try {
      await migrateMonth(luna);
      toast.success("Migrat");
      // Reload snapshots
      const r = await getSnapshots(store, luna);
      const map: Record<string, number> = {};
      (r.data || []).forEach((s: Snapshot) => { map[`${s.raionId}_${s.brandId}`] = s.nrFete; });
      setSnaps(map);
      setHasParentLegacy(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  };

  return (
    <div style={styles.card}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <label style={styles.lbl}>Magazin</label>
          <select value={store} onChange={(e) => setStore(e.target.value)} style={{ ...styles.select, minWidth: 280 }}>
            <option value="">— Alege magazin —</option>
            {stores.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label style={styles.lbl}>Luna</label>
          <select value={luna} onChange={(e) => setLuna(e.target.value)} style={styles.select}>
            {allMonths.map((m) => <option key={m} value={m}>{lunaLabel(m)}</option>)}
          </select>
        </div>
      </div>

      {!store && <p style={{ color: "var(--muted)" }}>Alege un magazin</p>}

      {store && (
        <>
          <div style={styles.infoBanner}>
            🏪 <b>{chain}</b> · se urmăresc <b>{relevantBrands.length}</b> brand-uri.
            {chain === "Alte" && <span style={{ color: "var(--muted)" }}> (rețea necunoscută)</span>}
          </div>

          {hasParentLegacy && (
            <div style={styles.warnBanner}>
              <span>⚠️ Există date salvate direct pe grup pentru <b>{lunaLabel(luna)}</b>. Pentru a folosi sub-raioanele, migrează-le în copilul default.</span>
              <button onClick={handleMigrate} style={styles.btnMigrate}>🔄 Migrează luna</button>
            </div>
          )}

          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, minWidth: 180 }}>Raion</th>
                {relevantBrands.map((b) => (
                  <th key={b.id} style={{ ...styles.th, color: b.color, textAlign: "center" }}>{b.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => {
                const kids = childrenOf[g.id] || [];
                if (!kids.length) {
                  return (
                    <tr key={g.id}>
                      <td style={{ ...styles.td, fontWeight: 700, color: "var(--accent)" }}>{g.name}</td>
                      {relevantBrands.map((b) => (
                        <td key={b.id} style={{ ...styles.td, textAlign: "center" }}>
                          <input type="number" min={0}
                            value={snaps[`${g.id}_${b.id}`] ?? 0}
                            onChange={(e) => handleChange(g.id, b.id, e.target.value)}
                            style={styles.numInput}
                          />
                        </td>
                      ))}
                    </tr>
                  );
                }
                return (
                  <>
                    {kids.map((c) => (
                      <tr key={c.id} style={{ background: "rgba(100,116,139,0.04)" }}>
                        <td style={{ ...styles.td, paddingLeft: 24 }}>↳ {c.name}</td>
                        {relevantBrands.map((b) => (
                          <td key={b.id} style={{ ...styles.td, textAlign: "center" }}>
                            <input type="number" min={0}
                              value={snaps[`${c.id}_${b.id}`] ?? 0}
                              onChange={(e) => handleChange(c.id, b.id, e.target.value)}
                              style={styles.numInput}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                    <tr key={`${g.id}-total`} style={{ background: "rgba(34,197,94,0.06)", borderTop: "2px solid var(--border)" }}>
                      <td style={{ ...styles.td, fontWeight: 700, color: "var(--accent)", textTransform: "uppercase" }}>
                        {g.name} <span style={{ fontSize: 10, color: "var(--muted)", fontWeight: 400 }}>(total auto)</span>
                      </td>
                      {relevantBrands.map((b) => (
                        <td key={b.id} style={{ ...styles.td, textAlign: "center", fontWeight: 700, color: "var(--green)" }}>
                          {groupTotal(g.id, b.id)}
                        </td>
                      ))}
                    </tr>
                  </>
                );
              })}
            </tbody>
          </table>

          <button onClick={handleSave} disabled={saving} style={styles.btnPrimary}>
            {saving ? "Se salvează…" : "💾 Salvează"}
          </button>
        </>
      )}
    </div>
  );
}

// ── Evolution tab ───────────────────────────────────────────────────────────

function EvolutionTab({ stores, config }: { stores: string[]; config: ConfigResponse }) {
  const [store, setStore] = useState("");
  const [raionId, setRaionId] = useState<UUID | "">("");
  const [data, setData] = useState<EvolutionResponse["data"]>([]);
  const [loading, setLoading] = useState(false);

  const raionOptions = useMemo(() => {
    const groups = config.raioane.filter((r) => !r.parentId)
      .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
    const kidsOf: Record<string, Raion[]> = {};
    for (const r of config.raioane) {
      if (r.parentId) (kidsOf[r.parentId] ||= []).push(r);
    }
    const opts: { id: UUID; label: string }[] = [];
    for (const g of groups) {
      opts.push({ id: g.id, label: `${g.name} (total)` });
      for (const c of (kidsOf[g.id] || [])) {
        opts.push({ id: c.id, label: `  ↳ ${c.name}` });
      }
    }
    return opts;
  }, [config]);

  useEffect(() => {
    if (!store) { setData([]); return; }
    setLoading(true);
    getEvolution(store, raionId || undefined)
      .then((r) => setData(r.data || []))
      .finally(() => setLoading(false));
  }, [store, raionId]);

  const byLuna = useMemo(() => {
    const map: Record<string, typeof data> = {};
    for (const row of data) (map[row.luna] ||= []).push(row);
    return Object.entries(map).sort((a, b) => b[0].localeCompare(a[0]));
  }, [data]);

  return (
    <div style={styles.card}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <label style={styles.lbl}>Magazin</label>
          <select value={store} onChange={(e) => setStore(e.target.value)} style={{ ...styles.select, minWidth: 280 }}>
            <option value="">— Alege magazin —</option>
            {stores.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label style={styles.lbl}>Raion</label>
          <select value={raionId} onChange={(e) => setRaionId(e.target.value as UUID)} style={styles.select}>
            <option value="">— Toate —</option>
            {raionOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {!store && <p style={{ color: "var(--muted)" }}>Selectează un magazin</p>}
      {loading && <p>Se încarcă…</p>}
      {store && !loading && !data.length && <p style={{ color: "var(--muted)" }}>Nu există date</p>}

      {byLuna.map(([luna, rows]) => (
        <div key={luna} style={{ marginBottom: 24 }}>
          <h4 style={{ color: "var(--accent)", marginBottom: 8 }}>{lunaLabel(luna)}</h4>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Raion</th>
                <th style={styles.th}>Brand</th>
                <th style={{ ...styles.th, textAlign: "right" }}>Fețe</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td style={styles.td}>{r.raionName}</td>
                  <td style={{ ...styles.td, color: r.brandColor }}>{r.brandName}</td>
                  <td style={{ ...styles.td, textAlign: "right", fontWeight: 600 }}>{r.nrFete}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

// ── Config tab ──────────────────────────────────────────────────────────────

function ConfigTab({
  config, reload, confirm,
}: {
  config: ConfigResponse;
  reload: () => Promise<void>;
  onEdit: () => void;
  onDelete: () => void;
  confirm: (opts: { title: string; message: string; danger?: boolean }) => Promise<boolean>;
}) {
  const toast = useToast();
  const [newRaionName, setNewRaionName] = useState("");
  const [newRaionParent, setNewRaionParent] = useState<UUID | "">("");
  const [newBrandName, setNewBrandName] = useState("");
  const [newBrandColor, setNewBrandColor] = useState("#888888");

  const groups = config.raioane.filter((r) => !r.parentId).sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
  const kidsOf = useMemo(() => {
    const c: Record<string, Raion[]> = {};
    for (const r of config.raioane) if (r.parentId) (c[r.parentId] ||= []).push(r);
    Object.values(c).forEach((arr) => arr.sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)));
    return c;
  }, [config]);

  const handleAddRaion = async () => {
    if (!newRaionName.trim()) return;
    await addRaion(newRaionName.trim(), newRaionParent || null);
    setNewRaionName("");
    await reload();
    toast.success("Adăugat");
  };

  const handleRaionUpdate = async (id: UUID, name: string) => {
    await updateRaion(id, name);
    await reload();
    toast.success("Actualizat");
  };

  const handleRaionDelete = async (id: UUID, name: string) => {
    const ok = await confirm({ title: "Ștergi raionul?", message: `Raion "${name}" + sub-raioanele + snapshot-urile atașate. Ireversibil.`, danger: true });
    if (!ok) return;
    await deleteRaion(id);
    await reload();
    toast.success("Șters");
  };

  const handleAddBrand = async () => {
    if (!newBrandName.trim()) return;
    await addBrand(newBrandName.trim(), newBrandColor);
    setNewBrandName("");
    setNewBrandColor("#888888");
    await reload();
    toast.success("Brand adăugat");
  };

  const handleBrandUpdate = async (id: UUID, name: string, color: string) => {
    await updateBrand(id, name, color);
    await reload();
    toast.success("Brand actualizat");
  };

  const handleBrandDelete = async (id: UUID, name: string) => {
    const ok = await confirm({ title: "Ștergi brandul?", message: `Brand "${name}" + snapshot-urile și matricea chain. Ireversibil.`, danger: true });
    if (!ok) return;
    await deleteBrand(id);
    await reload();
    toast.success("Șters");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        {/* Raioane */}
        <div style={{ ...styles.card, flex: 1, minWidth: 340 }}>
          <h3 style={{ color: "var(--accent)", marginBottom: 12 }}>🏬 Raioane</h3>
          {groups.map((g) => (
            <div key={g.id}>
              <RaionRow raion={g} isGroup onSave={handleRaionUpdate} onDelete={handleRaionDelete} />
              {(kidsOf[g.id] || []).map((c) => (
                <RaionRow key={c.id} raion={c} onSave={handleRaionUpdate} onDelete={handleRaionDelete} indent />
              ))}
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            <input placeholder="Raion nou…" value={newRaionName}
              onChange={(e) => setNewRaionName(e.target.value)}
              style={{ ...styles.input, flex: 1, minWidth: 140 }}
            />
            <select value={newRaionParent} onChange={(e) => setNewRaionParent(e.target.value as UUID)} style={styles.select}>
              <option value="">Grup nou</option>
              {groups.map((g) => <option key={g.id} value={g.id}>sub {g.name}</option>)}
            </select>
            <button onClick={handleAddRaion} style={styles.btnPrimary}>+ Adaugă</button>
          </div>
        </div>

        {/* Brands */}
        <div style={{ ...styles.card, flex: 1, minWidth: 340 }}>
          <h3 style={{ color: "var(--orange)", marginBottom: 12 }}>🏷️ Branduri</h3>
          {config.brands.map((b) => (
            <BrandRow key={b.id} brand={b} onSave={handleBrandUpdate} onDelete={handleBrandDelete} />
          ))}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <input placeholder="Brand nou…" value={newBrandName}
              onChange={(e) => setNewBrandName(e.target.value)}
              style={{ ...styles.input, flex: 1 }}
            />
            <input type="color" value={newBrandColor}
              onChange={(e) => setNewBrandColor(e.target.value)}
              style={{ width: 40, height: 36, border: "none", cursor: "pointer", background: "transparent" }}
            />
            <button onClick={handleAddBrand} style={styles.btnPrimary}>+ Adaugă</button>
          </div>
        </div>
      </div>

      {/* Chain × Brand matrix */}
      <ChainBrandsMatrix config={config} reload={reload} />
    </div>
  );
}

function RaionRow({
  raion, isGroup, indent, onSave, onDelete,
}: {
  raion: Raion; isGroup?: boolean; indent?: boolean;
  onSave: (id: UUID, name: string) => Promise<void>;
  onDelete: (id: UUID, name: string) => Promise<void>;
}) {
  const [name, setName] = useState(raion.name);
  useEffect(() => setName(raion.name), [raion.name]);
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: 8, paddingLeft: indent ? 32 : 8,
      borderBottom: "1px solid var(--border)",
      background: isGroup ? "var(--accent-soft)" : "transparent",
    }}>
      {isGroup && <span style={{ color: "var(--accent)", fontWeight: 700, fontSize: 10, width: 40 }}>GRUP</span>}
      {indent && <span style={{ color: "var(--muted)", fontSize: 11, width: 20 }}>↳</span>}
      <input value={name} onChange={(e) => setName(e.target.value)}
        style={{ flex: 1, padding: 6, fontSize: 13, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, fontWeight: isGroup ? 600 : 400 }}
      />
      <button onClick={() => onSave(raion.id, name)} style={styles.btnSmall}>💾</button>
      <button onClick={() => onDelete(raion.id, raion.name)} style={styles.btnSmallDanger}>🗑️</button>
    </div>
  );
}

function BrandRow({
  brand, onSave, onDelete,
}: {
  brand: Brand;
  onSave: (id: UUID, name: string, color: string) => Promise<void>;
  onDelete: (id: UUID, name: string) => Promise<void>;
}) {
  const [name, setName] = useState(brand.name);
  const [color, setColor] = useState(brand.color);
  useEffect(() => { setName(brand.name); setColor(brand.color); }, [brand.name, brand.color]);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 8, borderBottom: "1px solid var(--border)" }}>
      {brand.isOwn && <span style={{ color: "var(--green)", fontWeight: 700, fontSize: 10, width: 40 }}>PROPRIU</span>}
      <input type="color" value={color} onChange={(e) => setColor(e.target.value)}
        style={{ width: 32, height: 32, border: "none", cursor: "pointer", background: "transparent" }}
      />
      <input value={name} onChange={(e) => setName(e.target.value)}
        style={{ flex: 1, padding: 6, fontSize: 13, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4 }}
      />
      <button onClick={() => onSave(brand.id, name, color)} style={styles.btnSmall}>💾</button>
      <button onClick={() => onDelete(brand.id, brand.name)} style={styles.btnSmallDanger}>🗑️</button>
    </div>
  );
}

function ChainBrandsMatrix({ config, reload }: { config: ConfigResponse; reload: () => Promise<void> }) {
  const [matrix, setMatrix] = useState<Record<string, Set<UUID>>>(() => {
    const out: Record<string, Set<UUID>> = {};
    for (const ch of config.chains) out[ch] = new Set(config.chainBrands[ch] || []);
    return out;
  });
  const toast = useToast();

  const toggle = (chain: string, bid: UUID) => {
    setMatrix((prev) => {
      const s = new Set(prev[chain] || []);
      if (s.has(bid)) s.delete(bid); else s.add(bid);
      return { ...prev, [chain]: s };
    });
  };

  const handleSave = async () => {
    const payload: Record<string, UUID[]> = {};
    for (const [ch, s] of Object.entries(matrix)) payload[ch] = Array.from(s);
    await saveChainBrands(payload);
    await reload();
    toast.success("Matrice salvată");
  };

  return (
    <div style={styles.card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
        <h3 style={{ color: "#c084fc", margin: 0 }}>🔗 Branduri urmărite per rețea</h3>
        <button onClick={handleSave} style={{ ...styles.btnPrimary, background: "#c084fc", color: "#000" }}>💾 Salvează matricea</button>
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
        Bifează brandurile concurente pe care le măsori în fiecare rețea.
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Rețea</th>
              {config.brands.map((b) => (
                <th key={b.id} style={{ ...styles.th, textAlign: "center", color: b.color, minWidth: 80 }}>
                  {b.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {config.chains.map((ch) => (
              <tr key={ch}>
                <td style={{ ...styles.td, fontWeight: 600 }}>{ch}</td>
                {config.brands.map((b) => (
                  <td key={b.id} style={{ ...styles.td, textAlign: "center" }}>
                    <input type="checkbox"
                      checked={matrix[ch]?.has(b.id) || false}
                      onChange={() => toggle(ch, b.id)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Shared UI helpers ───────────────────────────────────────────────────────

function TabButton({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button onClick={onClick} style={{
      padding: "10px 20px", background: active ? "var(--card)" : "transparent",
      color: active ? "var(--accent)" : "var(--muted)",
      border: "none", borderBottom: `2px solid ${active ? "var(--accent)" : "transparent"}`,
      cursor: "pointer", fontWeight: 600, fontSize: 14,
    }}>{children}</button>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  page: {
    padding: "4px 4px 20px",
    color: "var(--text)",
    // Zoom out global pentru a încăpea matricea Sub-raion × Brand × P/A
    // (până la ~28 coloane) într-un singur view fără scroll orizontal.
    zoom: 0.80 as unknown as number,
  } as React.CSSProperties,
  title: { margin: "0 0 14px", fontSize: 17, fontWeight: 600, color: "var(--text)", letterSpacing: -0.2 } as React.CSSProperties,
  tabBar: {
    display: "flex", gap: 0, marginBottom: 18,
    borderBottom: "2px solid var(--border)", flexWrap: "wrap",
  } as React.CSSProperties,
  card: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 10, padding: 16, marginBottom: 14,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  } as React.CSSProperties,
  loading: { color: "var(--muted)", padding: 20 } as React.CSSProperties,
  error: { color: "var(--red)", padding: 12, background: "rgba(220,38,38,0.08)", borderRadius: 6 } as React.CSSProperties,
  empty: { textAlign: "center" as const, padding: 40, color: "var(--muted)" },
  globalBanner: {
    background: "linear-gradient(135deg, rgba(16,185,129,0.06), rgba(59,130,246,0.04))",
    border: "1px solid rgba(16,185,129,0.18)",
    borderRadius: 10, padding: "14px 18px", marginBottom: 16,
    boxShadow: "0 1px 3px rgba(0,0,0,0.03)",
  } as React.CSSProperties,
  chainHeader: {
    display: "flex", alignItems: "center", padding: 12,
    cursor: "pointer", borderBottom: "1px solid var(--border)",
  } as React.CSSProperties,
  select: { padding: "6px 10px", background: "var(--bg-elevated)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 13 } as React.CSSProperties,
  input: { padding: 8, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 13 } as React.CSSProperties,
  numInput: { width: 60, padding: 6, textAlign: "center" as const, background: "var(--bg)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 14, fontWeight: 600 },
  lbl: { display: "block", color: "var(--muted)", fontSize: 11, marginBottom: 4 } as React.CSSProperties,
  table: { width: "100%", borderCollapse: "collapse" as const },
  th: {
    textAlign: "left" as const, padding: "8px 10px", fontSize: 11,
    fontWeight: 600, color: "var(--muted)",
    borderBottom: "1px solid var(--border)", letterSpacing: 0.4, textTransform: "uppercase" as const,
  },
  td: { padding: "8px 10px", fontSize: 13, color: "var(--text)", borderBottom: "1px solid var(--border)" },
  btnPrimary: {
    padding: "8px 16px", background: "var(--accent)", color: "#fff",
    border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: 13,
    marginTop: 12,
  } as React.CSSProperties,
  btnSmall: { padding: "4px 8px", background: "var(--bg-elevated)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 12 } as React.CSSProperties,
  btnSmallDanger: { padding: "4px 8px", background: "transparent", color: "var(--red)", border: "1px solid var(--red)", borderRadius: 4, cursor: "pointer", fontSize: 12 } as React.CSSProperties,
  btnMigrate: { padding: "8px 16px", background: "#facc15", color: "#111", border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 700, fontSize: 12 } as React.CSSProperties,
  infoBanner: {
    marginBottom: 12, padding: "8px 12px",
    background: "rgba(251,146,60,0.08)", borderLeft: "3px solid var(--orange)",
    borderRadius: 4, fontSize: 12,
  } as React.CSSProperties,
  warnBanner: {
    marginBottom: 12, padding: "10px 14px",
    background: "rgba(250,204,21,0.1)", borderLeft: "3px solid #facc15",
    borderRadius: 4, fontSize: 13, display: "flex",
    justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap",
  } as React.CSSProperties,
  brandCell: (color: string): React.CSSProperties => ({
    padding: 10, background: "var(--bg-elevated)", border: `1px solid ${color}30`, borderRadius: 6,
  }),
  deltaLabel: (delta: number): React.CSSProperties => ({
    marginLeft: 8, fontSize: 12,
    color: delta > 0 ? "var(--green)" : delta < 0 ? "var(--red)" : "var(--muted)",
  }),
  deltaInline: (delta: number): React.CSSProperties => ({
    marginLeft: 6, fontSize: 11,
    color: delta > 0 ? "var(--green)" : delta < 0 ? "var(--red)" : "var(--muted)",
  }),
};
