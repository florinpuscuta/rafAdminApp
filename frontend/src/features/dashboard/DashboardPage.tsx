import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { CardSkeleton, Skeleton, TableSkeleton } from "../../shared/ui/Skeleton";
import { useAuth } from "../auth/AuthContext";
import { downloadDashboardReport, getOverview, listCategories, listChains } from "./api";
import { useToast } from "../../shared/ui/ToastProvider";
import MonthlyBarChart from "./MonthlyBarChart";
import type { DashboardOverview, TopChainRow } from "./types";

function fmtRON(amount: string): string {
  const n = Number(amount);
  if (Number.isNaN(n)) return amount;
  return n.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function computeDelta(cur: string, prev: string | null | undefined): number | null {
  if (prev == null) return null;
  const c = Number(cur);
  const p = Number(prev);
  if (Number.isNaN(c) || Number.isNaN(p) || p === 0) return null;
  return ((c - p) / p) * 100;
}

const MONTH_NAMES = ["Ian","Feb","Mar","Apr","Mai","Iun","Iul","Aug","Sep","Oct","Noi","Dec"];

interface ScopeState {
  storeId?: string;
  agentId?: string;
  productId?: string;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  const [data, setData] = useState<DashboardOverview | null>(null);
  const [year, setYear] = useState<number | null>(
    params.get("year") ? Number(params.get("year")) : null,
  );
  const [month, setMonth] = useState<number | null>(
    params.get("month") ? Number(params.get("month")) : null,
  );
  const [chain, setChain] = useState<string | null>(params.get("chain"));
  const [chains, setChains] = useState<string[]>([]);
  const [category, setCategory] = useState<string | null>(params.get("category"));
  const [categories, setCategories] = useState<string[]>([]);
  const [scope, setScope] = useState<ScopeState>({
    storeId: params.get("storeId") ?? undefined,
    agentId: params.get("agentId") ?? undefined,
    productId: params.get("productId") ?? undefined,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const syncUrl = useCallback(
    (y: number | null, m: number | null, c: string | null, cat: string | null, s: ScopeState) => {
      const p = new URLSearchParams();
      if (y != null) p.set("year", String(y));
      if (m != null) p.set("month", String(m));
      if (c) p.set("chain", c);
      if (cat) p.set("category", cat);
      if (s.storeId) p.set("storeId", s.storeId);
      if (s.agentId) p.set("agentId", s.agentId);
      if (s.productId) p.set("productId", s.productId);
      setParams(p, { replace: true });
    },
    [setParams],
  );

  const load = useCallback(
    async (y: number | null, m: number | null, c: string | null, cat: string | null, s: ScopeState) => {
      setLoading(true);
      setError(null);
      try {
        const d = await getOverview({
          year: y,
          month: m,
          chain: c,
          category: cat,
          storeId: s.storeId,
          agentId: s.agentId,
          productId: s.productId,
        });
        setData(d);
        if (y === null) setYear(d.year);
        syncUrl(y ?? d.year, m, c, cat, s);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
      } finally {
        setLoading(false);
      }
    },
    [syncUrl],
  );

  useEffect(() => {
    load(year, month, chain, category, scope);
    listChains().then(setChains).catch(() => {});
    listCategories().then(setCategories).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyScope(next: ScopeState) {
    setScope(next);
    load(year, month, chain, category, next);
  }

  function clearScope() {
    applyScope({});
  }

  async function handleExportWord() {
    try {
      await downloadDashboardReport({
        year,
        month,
        chain,
        category,
        storeId: scope.storeId,
        agentId: scope.agentId,
        productId: scope.productId,
      });
      toast.success("Raport descărcat");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la export");
    }
  }

  if (loading && !data) {
    return (
      <div>
        <Skeleton width={220} height={28} style={{ marginBottom: 16 }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          <CardSkeleton /><CardSkeleton /><CardSkeleton /><CardSkeleton />
        </div>
        <Skeleton height={200} radius={6} style={{ marginBottom: 20, display: "block" }} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          <TableSkeleton rows={5} cols={2} />
          <TableSkeleton rows={5} cols={2} />
          <TableSkeleton rows={5} cols={2} />
        </div>
      </div>
    );
  }
  if (error) return <p style={{ color: "#b00020" }}>{error}</p>;
  if (!data) return null;

  const hasData = data.kpis.totalRows > 0;

  return (
    <div>
      <header style={styles.header}>
        <div>
          <h2 style={{ margin: 0 }}>Salut, {user?.email}</h2>
          <p style={{ margin: "4px 0 0", color: "#666", fontSize: 14 }}>
            Sinteză vânzări — {data.year ?? "fără date"}
            {data.month != null && ` · ${MONTH_NAMES[data.month - 1]}`}
            {data.chain && ` · lanț ${data.chain}`}
            {data.category && ` · categorie ${data.category}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <label style={{ fontSize: 14 }}>
            An:{" "}
            <select
              value={year ?? ""}
              onChange={(e) => {
                const y = e.target.value ? Number(e.target.value) : null;
                setYear(y);
                load(y, month, chain, category, scope);
              }}
              disabled={data.availableYears.length === 0}
              style={styles.select}
            >
              {data.availableYears.length === 0 ? (
                <option>—</option>
              ) : (
                data.availableYears.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))
              )}
            </select>
          </label>
          <label style={{ fontSize: 14 }}>
            Luna:{" "}
            <select
              value={month ?? ""}
              onChange={(e) => {
                const m = e.target.value ? Number(e.target.value) : null;
                setMonth(m);
                load(year, m, chain, category, scope);
              }}
              style={styles.select}
            >
              <option value="">toate</option>
              {MONTH_NAMES.map((name, i) => (
                <option key={i + 1} value={i + 1}>{name}</option>
              ))}
            </select>
          </label>
          {chains.length > 0 && (
            <label style={{ fontSize: 14 }}>
              Lanț:{" "}
              <select
                value={chain ?? ""}
                onChange={(e) => {
                  const c = e.target.value || null;
                  setChain(c);
                  load(year, month, c, category, scope);
                }}
                style={styles.select}
              >
                <option value="">toate</option>
                {chains.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>
          )}
          {categories.length > 0 && (
            <label style={{ fontSize: 14 }}>
              Categorie:{" "}
              <select
                value={category ?? ""}
                onChange={(e) => {
                  const cat = e.target.value || null;
                  setCategory(cat);
                  load(year, month, chain, cat, scope);
                }}
                style={styles.select}
              >
                <option value="">toate</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </label>
          )}
          <button onClick={handleExportWord} style={styles.exportBtn} title="Descarcă raport Word">
            ↓ Word
          </button>
        </div>
      </header>

      {data.scope && (data.scope.storeId || data.scope.agentId || data.scope.productId) && (
        <div style={styles.scopeBreadcrumb}>
          <strong>Scope:</strong>{" "}
          {data.scope.storeName && <span>magazin <code>{data.scope.storeName}</code></span>}
          {data.scope.agentName && <span className="agent-private">agent <code>{data.scope.agentName}</code></span>}
          {data.scope.productName && (
            <span>produs <code>{data.scope.productCode} — {data.scope.productName}</code></span>
          )}
          <button onClick={clearScope} style={styles.clearBtn}>× Elimină scope</button>
        </div>
      )}

      {!hasData ? (
        <div style={styles.emptyBox}>
          <p style={{ margin: "0 0 8px" }}>
            Nu ai încă date. Încarcă un fișier Excel din <Link to="/sales">Vânzări</Link>.
          </p>
        </div>
      ) : (
        <>
          <section style={styles.kpiRow}>
            <Kpi
              label="Total valoare"
              value={`${fmtRON(data.kpis.totalAmount)} RON`}
              delta={computeDelta(data.kpis.totalAmount, data.compareKpis?.totalAmount)}
              compareYear={data.compareYear}
            />
            <Kpi
              label="Linii import"
              value={String(data.kpis.totalRows)}
              delta={computeDelta(
                String(data.kpis.totalRows),
                data.compareKpis ? String(data.compareKpis.totalRows) : null,
              )}
              compareYear={data.compareYear}
            />
            <Kpi label="Magazine canonice" value={String(data.kpis.distinctMappedStores)} />
            <span className="agent-section">
              <Kpi label="Agenți canonici" value={String(data.kpis.distinctMappedAgents)} />
            </span>
          </section>

          {(data.kpis.unmappedStoreRows > 0 || data.kpis.unmappedAgentRows > 0) && (
            <div style={styles.warnBox}>
              <strong>Date incomplete: </strong>
              {data.kpis.unmappedStoreRows > 0 && (
                <>
                  <Link to="/unmapped/stores">{data.kpis.unmappedStoreRows} linii fără magazin canonic</Link>
                  {data.kpis.unmappedAgentRows > 0 ? " · " : ""}
                </>
              )}
              {data.kpis.unmappedAgentRows > 0 && (
                <span className="agent-private">
                  <Link to="/unmapped/agents">{data.kpis.unmappedAgentRows} linii fără agent canonic</Link>
                </span>
              )}
            </div>
          )}

          <div style={{ marginBottom: 12 }}>
            <MonthlyBarChart
              data={data.monthlyTotals}
              compare={data.compareYear !== null ? data.monthlyTotalsCompare : null}
              cyLabel={String(data.year)}
              pyLabel={data.compareYear != null ? String(data.compareYear) : undefined}
            />
          </div>

          {data.topChains.length > 0 && (
            <div style={styles.chainsBox}>
              <h3 style={{ margin: "0 0 10px" }}>Vânzări pe lanț</h3>
              <ChainsBars
                rows={data.topChains}
                selectedChain={data.chain}
                onSelect={(c) => {
                  setChain(c);
                  load(year, month, c, category, scope);
                }}
              />
            </div>
          )}

          <div style={styles.columns}>
            <TopTable
              title="Top magazine"
              rows={data.topStores.map((s) => ({
                primary: s.storeName,
                secondary: s.chain ?? (s.storeId ? "" : "—"),
                amount: s.totalAmount,
                count: s.rowCount,
                muted: s.storeId === null,
                onClick: s.storeId
                  ? () => applyScope({ storeId: s.storeId ?? undefined })
                  : undefined,
              }))}
            />
            <div className="agent-section" style={{ display: "contents" }}>
              <TopTable
                title="Top agenți"
                rows={data.topAgents.map((a) => ({
                  primary: a.agentName,
                  secondary: "",
                  amount: a.totalAmount,
                  count: a.rowCount,
                  muted: a.agentId === null,
                  onClick: a.agentId
                    ? () => applyScope({ agentId: a.agentId ?? undefined })
                    : undefined,
                }))}
              />
            </div>
            <TopTable
              title="Top produse"
              rows={data.topProducts.map((p) => ({
                primary: p.productName,
                secondary: `${p.productCode}${p.category ? " · " + p.category : ""}`,
                amount: p.totalAmount,
                count: p.rowCount,
                muted: p.productId === null,
                onClick: p.productId
                  ? () => applyScope({ productId: p.productId ?? undefined })
                  : undefined,
              }))}
            />
          </div>
        </>
      )}
    </div>
  );
}

function ChainsBars({
  rows,
  selectedChain,
  onSelect,
}: {
  rows: TopChainRow[];
  selectedChain?: string | null;
  onSelect?: (chain: string | null) => void;
}) {
  const max = Math.max(...rows.map((r) => Number(r.totalAmount) || 0), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {rows.map((r) => {
        const v = Number(r.totalAmount) || 0;
        const pct = (v / max) * 100;
        const isUnmapped = r.chain === "Nemapate" || r.chain === "Fără lanț";
        const clickable = !isUnmapped && !!onSelect;
        const isSelected = selectedChain === r.chain;
        return (
          <div
            key={r.chain}
            onClick={
              clickable
                ? () => onSelect!(isSelected ? null : r.chain)
                : undefined
            }
            style={{
              display: "grid",
              gridTemplateColumns: "160px 1fr 220px",
              gap: 12,
              alignItems: "center",
              padding: "4px 8px",
              borderRadius: 4,
              cursor: clickable ? "pointer" : "default",
              background: isSelected ? "#eff6ff" : "transparent",
              border: isSelected ? "1px solid #93c5fd" : "1px solid transparent",
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 500, color: isUnmapped ? "#999" : "#222" }}>
              {r.chain}
              {isSelected && " ◉"}
            </div>
            <div style={{ height: 14, background: "#f1f5f9", borderRadius: 3, position: "relative" }}>
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: isUnmapped ? "#cbd5e1" : isSelected ? "#1e40af" : "#2563eb",
                  borderRadius: 3,
                }}
              />
            </div>
            <div style={{ fontSize: 12, color: "#555", fontVariantNumeric: "tabular-nums", textAlign: "right" }}>
              {fmtRON(r.totalAmount)} RON · {r.storeCount} mag · {r.rowCount} linii
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Kpi({
  label,
  value,
  delta,
  compareYear,
}: {
  label: string;
  value: string;
  delta?: number | null;
  compareYear?: number | null;
}) {
  const deltaColor = delta == null ? "#888" : delta > 0 ? "#0a7f2e" : delta < 0 ? "#b00020" : "#888";
  const deltaSign = delta != null && delta > 0 ? "↑" : delta != null && delta < 0 ? "↓" : "";
  return (
    <div style={styles.kpiCard}>
      <div style={{ fontSize: 10.5, color: "#666", textTransform: "uppercase", lineHeight: 1.2 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2, lineHeight: 1.15 }}>{value}</div>
      {delta != null && (
        <div style={{ fontSize: 10.5, color: deltaColor, marginTop: 2, lineHeight: 1.2 }}>
          {deltaSign} {Math.abs(delta).toFixed(1)}% vs {compareYear ?? "PY"}
        </div>
      )}
    </div>
  );
}

interface TopRow {
  primary: string;
  secondary: string;
  amount: string;
  count: number;
  muted: boolean;
  onClick?: () => void;
}

function TopTable({ title, rows }: { title: string; rows: TopRow[] }) {
  return (
    <div style={styles.topBox}>
      <h3 style={{ margin: "0 0 10px" }}>{title}</h3>
      {rows.length === 0 ? (
        <p style={{ color: "#999", fontSize: 14 }}>—</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {rows.map((r, i) => {
            const clickable = !!r.onClick;
            const base: React.CSSProperties = {
              display: "flex",
              gap: 12,
              padding: "8px 0",
              borderBottom: "1px solid #f1f1f1",
              alignItems: "flex-start",
              cursor: clickable ? "pointer" : "default",
              color: r.muted ? "#999" : undefined,
            };
            return (
              <div
                key={i}
                style={base}
                onClick={r.onClick}
                onMouseEnter={
                  clickable
                    ? (e) => {
                        (e.currentTarget as HTMLDivElement).style.background = "#f8fafc";
                      }
                    : undefined
                }
                onMouseLeave={
                  clickable
                    ? (e) => {
                        (e.currentTarget as HTMLDivElement).style.background = "transparent";
                      }
                    : undefined
                }
              >
                <div style={{ flex: 1, minWidth: 0, fontSize: 13, lineHeight: 1.35 }}>
                  <div style={{ wordBreak: "break-word" }}>{r.primary}</div>
                  {r.secondary && (
                    <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>
                      {r.secondary}
                    </div>
                  )}
                </div>
                <div
                  style={{
                    flex: "0 0 128px",
                    textAlign: "right",
                    fontSize: 13,
                    whiteSpace: "nowrap",
                    fontVariantNumeric: "tabular-nums",
                    lineHeight: 1.35,
                  }}
                >
                  <div style={{ fontWeight: 500 }}>
                    {fmtRON(r.amount)}{" "}
                    <span style={{ color: "#888", fontWeight: 400, fontSize: 11 }}>RON</span>
                  </div>
                  <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>
                    {r.count} linii
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginBottom: 20,
  },
  select: { padding: 6, fontSize: 14 },
  exportBtn: {
    padding: "6px 14px",
    fontSize: 13,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #d0d0d0",
    borderRadius: 4,
  },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 12,
    marginBottom: 16,
  },
  kpiCard: {
    padding: "8px 10px",
    background: "#fff",
    border: "1px solid #eee",
    borderRadius: 6,
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minHeight: 58,
  },
  warnBox: {
    padding: "10px 14px",
    background: "#fff6e5",
    border: "1px solid #f0c674",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
  columns: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 },
  topBox: {
    padding: 16,
    background: "#fff",
    border: "1px solid #eee",
    borderRadius: 6,
  },
  chainsBox: {
    padding: 16,
    background: "#fff",
    border: "1px solid #eee",
    borderRadius: 6,
    marginBottom: 12,
  },
  scopeBreadcrumb: {
    padding: "10px 14px",
    background: "#eff6ff",
    border: "1px solid #93c5fd",
    borderRadius: 6,
    marginBottom: 12,
    fontSize: 14,
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  clearBtn: {
    marginLeft: "auto",
    padding: "4px 10px",
    fontSize: 12,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #93c5fd",
    borderRadius: 3,
    color: "#1e40af",
  },
  topTd: { padding: "8px 0", borderBottom: "1px solid #f1f1f1", fontSize: 14 },
  emptyBox: {
    padding: 24,
    background: "var(--bg-elevated, #fafafa)",
    border: "1px dashed var(--border, #ccc)",
    borderRadius: 6,
  },
  demoBtn: {
    padding: "8px 16px", fontSize: 14, cursor: "pointer",
    background: "#2563eb", color: "#fff", border: "none", borderRadius: 4,
  },
};
