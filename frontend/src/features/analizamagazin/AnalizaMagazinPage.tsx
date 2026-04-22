import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
} from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getAnalizaMagazin, getStores } from "./api";
import type {
  AMGapProduct,
  AMResponse,
  AMScope,
  AMStoreOption,
} from "./types";

function scopeFromCompany(c: CompanyScope): AMScope {
  // sikadp nu are pagină — fallback pe adp dacă apare (protejăm runtime-ul).
  if (c === "sika") return "sika";
  return "adp";
}

function scopeLabel(s: AMScope): string {
  return s === "sika" ? "Sika" : "Adeplast";
}

function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function fmtRo(n: number, maxFrac = 0): string {
  return new Intl.NumberFormat("ro-RO", {
    maximumFractionDigits: maxFrac,
  }).format(n);
}

const CHAIN_COLORS: Record<string, string> = {
  Dedeman: "#22c55e",
  Altex: "#ef4444",
  "Leroy Merlin": "#3b82f6",
  Hornbach: "#f59e0b",
};

const MONTHS_OPTIONS: number[] = [3, 6, 9, 12];

export default function AnalizaMagazinPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);

  const [monthsWindow, setMonthsWindow] = useState<number>(3);
  const [stores, setStores] = useState<AMStoreOption[]>([]);
  const [selectedStore, setSelectedStore] = useState<string>("");
  const [data, setData] = useState<AMResponse | null>(null);
  const [loadingStores, setLoadingStores] = useState(true);
  const [loadingGap, setLoadingGap] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Set de categorii/TM-uri bifate. String gol = produse fără categorie.
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());

  // Încărcăm lista de magazine când se schimbă scope-ul sau fereastra.
  useEffect(() => {
    let cancelled = false;
    setLoadingStores(true);
    setError(null);
    setData(null);
    getStores(apiScope, monthsWindow)
      .then((r) => {
        if (cancelled) return;
        setStores(r.stores);
        setSelectedStore((prev) => {
          if (prev && r.stores.some((s) => s.key === prev)) return prev;
          return r.stores[0]?.key ?? "";
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare magazine");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingStores(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiScope, monthsWindow]);

  // Încărcăm gap-ul când se schimbă magazinul sau fereastra.
  useEffect(() => {
    if (!selectedStore) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoadingGap(true);
    setError(null);
    getAnalizaMagazin(apiScope, selectedStore, monthsWindow)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare gap");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingGap(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiScope, selectedStore, monthsWindow]);

  const selectedStoreAgent = useMemo<string | null>(() => {
    return stores.find((s) => s.key === selectedStore)?.agent ?? null;
  }, [stores, selectedStore]);

  // Grupăm magazinele pentru <optgroup>.
  const storesByChain = useMemo(() => {
    const groups: Record<string, AMStoreOption[]> = {};
    for (const s of stores) {
      (groups[s.chain] ??= []).push(s);
    }
    return groups;
  }, [stores]);

  const availableCategories = useMemo<string[]>(() => {
    if (!data) return [];
    const labeled: string[] = [];
    let hasNone = false;
    for (const b of data.breakdown) {
      if (b.category == null) hasNone = true;
      else labeled.push(b.category);
    }
    labeled.sort((a, b) => a.localeCompare(b));
    if (hasNone) labeled.push("");
    return labeled;
  }, [data]);

  // La sosirea unui răspuns nou pornim cu toate categoriile/TM-urile DEBIFATE;
  // utilizatorul alege explicit ce vrea să vadă.
  useEffect(() => {
    setSelectedCategories(new Set());
  }, [data]);

  const filteredGap = useMemo<AMGapProduct[]>(() => {
    if (!data) return [];
    return data.gap.filter((p) => selectedCategories.has(p.category ?? ""));
  }, [data, selectedCategories]);

  // GAP per categorie — cheia "" = „fără categorie".
  const gapByCategory = useMemo<Map<string, number>>(() => {
    const m = new Map<string, number>();
    if (!data) return m;
    for (const b of data.breakdown) {
      m.set(b.category ?? "", b.gapCount);
    }
    return m;
  }, [data]);

  // Sumar recalculat pe baza categoriilor bifate.
  const filteredTotals = useMemo(() => {
    if (!data) {
      return { chainSkuCount: 0, ownSkuCount: 0, gapCount: 0 };
    }
    let chainSkuCount = 0;
    let ownSkuCount = 0;
    let gapCount = 0;
    for (const b of data.breakdown) {
      const key = b.category ?? "";
      if (!selectedCategories.has(key)) continue;
      chainSkuCount += b.chainSkuCount;
      ownSkuCount += b.ownSkuCount;
      gapCount += b.gapCount;
    }
    return { chainSkuCount, ownSkuCount, gapCount };
  }, [data, selectedCategories]);

  function toggleCategory(c: string) {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(c)) next.delete(c);
      else next.add(c);
      return next;
    });
  }

  function selectAllCategories() {
    setSelectedCategories(new Set(availableCategories));
  }

  function clearCategories() {
    setSelectedCategories(new Set());
  }

  const categoryLabelName = apiScope === "sika" ? "Target Market" : "Categorie";

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} — Analiza Magazin (gap sortimentație, ultimele {monthsWindow} luni)
        </h1>
      </div>

      <div style={styles.controls}>
        <div style={styles.label}>
          Fereastră
          <div style={styles.btnGroup} role="group" aria-label="Selectează fereastra de analiză">
            {MONTHS_OPTIONS.map((m) => {
              const active = m === monthsWindow;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMonthsWindow(m)}
                  aria-pressed={active}
                  style={{
                    ...styles.monthBtn,
                    ...(active ? styles.monthBtnActive : {}),
                  }}
                >
                  {m} luni
                </button>
              );
            })}
          </div>
        </div>

      </div>

      <div style={styles.magazinRow}>
        <div style={styles.magazinLabelRow}>
          <span style={styles.magazinLabel}>Magazin</span>
          {selectedStoreAgent && (
            <span style={styles.magazinAgentInline}>
              <span style={styles.magazinAgentLabel}>Agent:</span> {selectedStoreAgent}
            </span>
          )}
        </div>
        <select
          data-wide="true"
          value={selectedStore}
          onChange={(e) => setSelectedStore(e.target.value)}
          disabled={loadingStores || stores.length === 0}
          style={styles.selectWide}
        >
          {stores.length === 0 && !loadingStores && (
            <option value="">(niciun magazin cu vânzări în ultimele 3 luni)</option>
          )}
          {Object.entries(storesByChain).map(([chain, items]) => (
            <optgroup key={chain} label={chain}>
              {items.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}{s.agent ? ` — ${s.agent}` : ""}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {data && availableCategories.length > 0 && (
        <div style={styles.filterBar}>
          <div style={styles.filterHeader}>
            <span style={styles.filterTitle}>{categoryLabelName}</span>
            <div style={styles.filterActions}>
              <button
                type="button"
                onClick={selectAllCategories}
                style={styles.linkBtn}
              >
                Toate
              </button>
              <span style={styles.filterSep}>·</span>
              <button
                type="button"
                onClick={clearCategories}
                style={styles.linkBtn}
              >
                Niciuna
              </button>
            </div>
          </div>
          <div style={styles.chipRow}>
            {availableCategories.map((c) => {
              const active = selectedCategories.has(c);
              const label = c === "" ? "(fără categorie)" : c;
              const gap = gapByCategory.get(c) ?? 0;
              return (
                <label
                  key={c || "_none"}
                  style={{
                    ...styles.chip,
                    ...(active ? styles.chipActive : {}),
                  }}
                >
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => toggleCategory(c)}
                    style={styles.chipInput}
                  />
                  <span style={styles.chipBox} aria-hidden="true">
                    {active ? "✓" : ""}
                  </span>
                  <span style={styles.chipLabel}>{label}</span>
                  {gap > 0 && (
                    <span style={styles.chipGap} title="Produse lipsă în această categorie">
                      {gap}
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      )}

      {error && <div style={styles.error}>{error}</div>}
      {loadingStores && !stores.length && <div style={styles.loading}>Se încarcă magazinele…</div>}
      {loadingGap && <div style={styles.loading}>Se calculează gap-ul…</div>}

      {data && !loadingGap && (
        <>
          <SummaryCard
            data={data}
            agent={selectedStoreAgent}
            chainSkuCount={filteredTotals.chainSkuCount}
            ownSkuCount={filteredTotals.ownSkuCount}
            gapCount={filteredTotals.gapCount}
          />
          <GapCard
            products={filteredGap}
            totalCount={data.gap.length}
            visibleCount={filteredGap.length}
          />
        </>
      )}
    </div>
  );
}

function SummaryCard({
  data,
  agent,
  chainSkuCount,
  ownSkuCount,
  gapCount,
}: {
  data: AMResponse;
  agent: string | null;
  chainSkuCount: number;
  ownSkuCount: number;
  gapCount: number;
}) {
  const color = CHAIN_COLORS[data.chain] ?? "#94a3b8";
  const gapPct =
    chainSkuCount > 0
      ? Math.round((gapCount / chainSkuCount) * 1000) / 10
      : 0;
  return (
    <div style={styles.card}>
      <div style={styles.summaryRow}>
        <div style={styles.summaryBlock}>
          <div style={styles.summaryLabel}>Magazin</div>
          <div style={styles.summaryValue}>{data.store}</div>
          <div style={{ ...styles.summaryChain, color }}>
            <span style={{ ...styles.chainDot, background: color }} /> {data.chain}
          </div>
          {agent && (
            <div style={styles.summaryAgent}>
              <span style={styles.summaryAgentLabel}>Agent:</span> {agent}
            </div>
          )}
        </div>
        <div style={styles.summaryBlock}>
          <div style={styles.summaryLabel}>SKU-uri pe lanț</div>
          <div style={styles.summaryValueBig}>{fmtRo(chainSkuCount)}</div>
        </div>
        <div style={styles.summaryBlock}>
          <div style={styles.summaryLabel}>SKU-uri la tine</div>
          <div style={styles.summaryValueBig}>{fmtRo(ownSkuCount)}</div>
        </div>
        <div style={{ ...styles.summaryBlock, ...styles.summaryGap }}>
          <div style={styles.summaryLabel}>GAP</div>
          <div style={{ ...styles.summaryValueBig, color: "#ef4444" }}>
            {fmtRo(gapCount)}
          </div>
          <div style={styles.summaryPct}>{gapPct}% din sortimentul lanțului</div>
        </div>
      </div>
    </div>
  );
}

function GapCard({
  products,
  totalCount,
  visibleCount,
}: {
  products: AMGapProduct[];
  totalCount: number;
  visibleCount: number;
}) {
  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <h2 style={styles.cardTitle}>
          Produse lipsă {visibleCount !== totalCount ? `(${visibleCount} / ${totalCount})` : `(${totalCount})`}
        </h2>
      </div>
      {products.length === 0 ? (
        <div style={styles.empty}>
          Niciun produs lipsă{totalCount > 0 ? " pentru filtrul curent" : ""}.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>COD</th>
                <th style={styles.th}>PRODUS</th>
                <th style={styles.th}>CATEG.</th>
                <th style={styles.thNum}>CANT. LANȚ</th>
                <th style={styles.thNum}>VALOARE LANȚ</th>
                <th style={styles.thNum}>MAG. CARE VÂND</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.productId}>
                  <td style={styles.tdCode}>{p.productCode || "—"}</td>
                  <td style={styles.td}>{p.productName || "—"}</td>
                  <td style={styles.tdCat}>{p.category ?? "—"}</td>
                  <td style={styles.tdNum}>{fmtRo(toNum(p.chainQty), 0)}</td>
                  <td style={styles.tdNum}>{fmtRo(toNum(p.chainValue), 0)}</td>
                  <td style={styles.tdNum}>{p.storesSellingCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { padding: "4px 0 40px" },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
    flexWrap: "wrap",
    gap: 10,
  },
  title: {
    margin: 0,
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text)",
  },
  controls: {
    display: "flex",
    gap: 12,
    alignItems: "flex-end",
    flexWrap: "wrap",
    marginBottom: 14,
  },
  label: {
    display: "flex",
    flexDirection: "column",
    fontSize: 11,
    color: "var(--muted)",
    fontWeight: 600,
    letterSpacing: 0.3,
    textTransform: "uppercase",
    gap: 4,
    minWidth: 260,
  },
  magazinRow: {
    display: "block",
    width: "100%",
    marginBottom: 14,
  },
  magazinLabelRow: {
    display: "flex",
    alignItems: "baseline",
    gap: 12,
    flexWrap: "wrap",
    marginBottom: 4,
  },
  magazinLabel: {
    fontSize: 11,
    color: "var(--muted)",
    fontWeight: 600,
    letterSpacing: 0.3,
    textTransform: "uppercase",
  },
  magazinAgentInline: {
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text)",
  },
  selectWide: {
    display: "block",
    padding: "8px 12px",
    fontSize: 13,
    background: "var(--card)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 5,
    width: "100%",
    boxSizing: "border-box",
  },
  magazinAgentLabel: {
    color: "var(--muted)",
    fontWeight: 600,
    letterSpacing: 0.3,
    textTransform: "uppercase",
    fontSize: 10.5,
    marginRight: 4,
  },
  btnGroup: {
    display: "inline-flex",
    gap: 0,
    border: "1px solid var(--border)",
    borderRadius: 5,
    overflow: "hidden",
    background: "var(--card)",
  },
  monthBtn: {
    padding: "7px 14px",
    fontSize: 13,
    fontWeight: 600,
    background: "transparent",
    color: "var(--muted)",
    border: "none",
    borderRight: "1px solid var(--border)",
    cursor: "pointer",
    fontVariantNumeric: "tabular-nums",
  },
  monthBtnActive: {
    background: "var(--accent-soft)",
    color: "var(--cyan)",
  },
  filterBar: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    padding: "10px 12px",
    marginBottom: 14,
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 6,
  },
  filterHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  filterTitle: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.4,
    textTransform: "uppercase",
    color: "var(--muted)",
  },
  filterActions: {
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
  filterSep: { color: "var(--muted)", fontSize: 12 },
  linkBtn: {
    background: "transparent",
    border: "none",
    padding: "2px 6px",
    fontSize: 12,
    fontWeight: 600,
    color: "var(--cyan)",
    cursor: "pointer",
  },
  chipRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: 8,
    alignItems: "center",
  },
  chip: {
    boxSizing: "border-box",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 12px",
    fontSize: 12.5,
    fontWeight: 600,
    background: "transparent",
    color: "var(--muted)",
    border: "1px solid var(--border)",
    borderRadius: 999,
    cursor: "pointer",
    whiteSpace: "nowrap",
    flexShrink: 0,
    flexGrow: 0,
    lineHeight: 1.2,
    userSelect: "none",
    width: "auto",
    maxWidth: "100%",
  },
  chipInput: {
    position: "absolute",
    width: 1,
    height: 1,
    padding: 0,
    margin: -1,
    overflow: "hidden",
    clip: "rect(0 0 0 0)",
    whiteSpace: "nowrap",
    border: 0,
  },
  chipLabel: {
    whiteSpace: "nowrap",
  },
  chipActive: {
    background: "var(--accent-soft)",
    color: "var(--cyan)",
    borderColor: "var(--cyan)",
  },
  chipBox: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 14,
    height: 14,
    fontSize: 11,
    fontWeight: 700,
    borderRadius: 3,
    border: "1px solid currentColor",
    lineHeight: 1,
  },
  chipGap: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    minWidth: 22,
    height: 18,
    padding: "0 7px",
    marginLeft: 4,
    fontSize: 11.5,
    fontWeight: 800,
    color: "#ffffff",
    background: "#ef4444",
    border: "1px solid #dc2626",
    borderRadius: 999,
    fontVariantNumeric: "tabular-nums",
    lineHeight: 1,
    flexShrink: 0,
  },
  error: {
    padding: 10,
    background: "rgba(239,68,68,0.1)",
    border: "1px solid #ef4444",
    color: "#ef4444",
    borderRadius: 5,
    marginBottom: 12,
    fontSize: 13,
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
  summaryRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 14,
  },
  summaryBlock: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    padding: "6px 10px",
    borderLeft: "2px solid var(--border)",
  },
  summaryGap: {
    borderLeft: "2px solid #ef4444",
    background: "rgba(239,68,68,0.05)",
    borderRadius: 4,
  },
  summaryLabel: {
    fontSize: 10.5,
    color: "var(--muted)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    fontWeight: 600,
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
  },
  summaryValueBig: {
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text)",
    fontVariantNumeric: "tabular-nums",
  },
  summaryChain: {
    fontSize: 12,
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  summaryAgent: {
    fontSize: 12,
    fontWeight: 500,
    color: "var(--text)",
    marginTop: 2,
  },
  summaryAgentLabel: {
    color: "var(--muted)",
    fontWeight: 600,
    letterSpacing: 0.3,
    textTransform: "uppercase",
    fontSize: 10.5,
    marginRight: 4,
  },
  chainDot: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    display: "inline-block",
  },
  summaryPct: {
    fontSize: 11,
    color: "var(--muted)",
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
    padding: "6px 8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  tdCode: {
    padding: "6px 8px",
    fontSize: 12,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    fontFamily: "var(--font-mono, monospace)",
    whiteSpace: "nowrap",
  },
  tdCat: {
    padding: "6px 8px",
    fontSize: 12,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    whiteSpace: "nowrap",
  },
  tdNum: {
    padding: "6px 8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    whiteSpace: "nowrap",
  },
  empty: {
    padding: 20,
    textAlign: "center",
    color: "var(--muted)",
    fontSize: 13,
  },
};
