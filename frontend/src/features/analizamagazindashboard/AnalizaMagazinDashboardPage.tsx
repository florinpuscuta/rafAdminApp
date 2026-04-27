import {
  Fragment,
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
} from "react";

import { ApiError } from "../../shared/api";
import { useSelectedStore } from "../../shared/hooks/useSelectedStore";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { StoreInsightsCard } from "../../shared/ui/StoreInsightsCard";
import { getClients, getDashboard, getStoresForClient } from "./api";
import type {
  AMDDashboardResponse,
  AMDMetrics,
  AMDScope,
  AMDStoreOption,
} from "./types";


const MONTHS_OPTIONS: number[] = [3, 6, 9, 12];
const MONTH_NAMES: string[] = [
  "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];


function scopeFromCompany(c: CompanyScope): AMDScope {
  if (c === "sika") return "sika";
  return "adp";
}

/** Detectează chain-ul (client KA) dintr-un nume brut de magazin. */
function clientFromStoreName(name: string): string {
  const upper = name.toUpperCase();
  if (upper.includes("DEDEMAN")) return "Dedeman";
  if (upper.includes("ALTEX")) return "Altex";
  if (upper.includes("LEROY") || upper.includes("MERLIN")) return "Leroy Merlin";
  if (upper.includes("HORNBACH")) return "Hornbach";
  return "";
}

function scopeLabel(s: AMDScope): string {
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

function pctDelta(curr: number, prev: number): number | null {
  if (prev === 0) return null;
  return ((curr - prev) / prev) * 100;
}

function fmtPct(p: number | null): string {
  if (p == null) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${p.toFixed(1)}%`;
}

function deltaColor(p: number | null): string {
  if (p == null) return "#94a3b8";
  if (p > 0) return "#16a34a";
  if (p < 0) return "#dc2626";
  return "#94a3b8";
}


export default function AnalizaMagazinDashboardPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);

  const [monthsWindow, setMonthsWindow] = useState<number>(3);

  const [clients, setClients] = useState<string[]>([]);
  const [selectedClient, setSelectedClient] = useState<string>("");

  const [stores, setStores] = useState<AMDStoreOption[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<string>("");

  // Sincronizat cu /analiza/magazin prin localStorage (numele magazinului).
  const { selectedStore: persistedStoreName, setSelectedStore: setPersistedStoreName } =
    useSelectedStore();

  const [data, setData] = useState<AMDDashboardResponse | null>(null);

  const [loadingClients, setLoadingClients] = useState(true);
  const [loadingStores, setLoadingStores] = useState(false);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lista de clienți (Dedeman/Altex/Leroy/Hornbach) — fixă la nivel SaaS.
  useEffect(() => {
    let cancelled = false;
    setLoadingClients(true);
    setError(null);
    getClients()
      .then((r) => {
        if (cancelled) return;
        setClients(r.clients);
        // Dacă vine un magazin pre-selectat din /analiza/magazin (localStorage),
        // încercăm să detectăm clientul (chain) corespunzător.
        setSelectedClient((prev) => {
          if (prev) return prev;
          if (persistedStoreName) {
            const detected = clientFromStoreName(persistedStoreName);
            if (detected && r.clients.includes(detected)) return detected;
          }
          return r.clients[0] || "";
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare clienți");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingClients(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Magazinele pentru clientul selectat (din `store_agent_mappings`).
  useEffect(() => {
    if (!selectedClient) {
      setStores([]);
      setSelectedStoreId("");
      return;
    }
    let cancelled = false;
    setLoadingStores(true);
    setError(null);
    setData(null);
    getStoresForClient(selectedClient)
      .then((r) => {
        if (cancelled) return;
        setStores(r.stores);
        setSelectedStoreId((prev) => {
          if (prev && r.stores.some((s) => s.storeId === prev)) return prev;
          // Sincronizare cu /analiza/magazin: dacă persistedStoreName se
          // potrivește cu un magazin din listă, îl pre-selectăm.
          if (persistedStoreName) {
            const match = r.stores.find((s) => s.name === persistedStoreName);
            if (match) return match.storeId;
          }
          return r.stores[0]?.storeId ?? "";
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
  }, [selectedClient]);

  // Dashboard data — declanșat de orice schimbare a magazinului/ferestrei/scope-ului.
  useEffect(() => {
    if (!selectedStoreId) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoadingDashboard(true);
    setError(null);
    getDashboard(apiScope, selectedStoreId, monthsWindow)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare dashboard");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDashboard(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiScope, selectedStoreId, monthsWindow]);

  const windowLabel = useMemo<string>(() => {
    if (!data || data.windowCurr.length === 0) return "—";
    const first = data.windowCurr[0];
    const last = data.windowCurr[data.windowCurr.length - 1];
    const mFirst = MONTH_NAMES[first.month] ?? String(first.month);
    const mLast = MONTH_NAMES[last.month] ?? String(last.month);
    if (first.year === last.year) {
      return `${mFirst}–${mLast} ${first.year}`;
    }
    return `${mFirst} ${first.year} – ${mLast} ${last.year}`;
  }, [data]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>
          {scopeLabel(apiScope)} — Dashboard Magazin
        </h1>
        {data && (
          <span style={styles.subtitle}>
            <strong style={styles.storeNameBig}>{data.storeName}</strong>
            <span style={styles.subtitleMeta}>
              · {windowLabel} · {data.monthsWindow} luni
            </span>
          </span>
        )}
      </div>

      <div style={styles.controls}>
        <div style={styles.controlBlock}>
          <span style={styles.controlLabel}>Fereastră</span>
          <div style={styles.btnGroup} role="group">
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

        <div style={styles.controlBlock}>
          <span style={styles.controlLabel}>Client</span>
          <select
            value={selectedClient}
            onChange={(e) => setSelectedClient(e.target.value)}
            disabled={loadingClients || clients.length === 0}
            data-wide="true"
            style={styles.select}
          >
            {clients.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        <div style={{ ...styles.controlBlock, flex: 1, minWidth: 320 }}>
          <span style={styles.controlLabel}>Magazin</span>
          <select
            value={selectedStoreId}
            onChange={(e) => {
              const newId = e.target.value;
              setSelectedStoreId(newId);
              // Sincronizăm numele în localStorage (citit de /analiza/magazin).
              const found = stores.find((s) => s.storeId === newId);
              setPersistedStoreName(found?.name ?? "");
            }}
            disabled={loadingStores || stores.length === 0}
            data-wide="true"
            style={styles.selectWide}
          >
            {stores.length === 0 && !loadingStores && (
              <option value="">(niciun magazin pentru acest client)</option>
            )}
            {stores.map((s) => (
              <option key={s.storeId} value={s.storeId}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {(loadingDashboard || loadingStores) && (
        <div style={styles.loading}>Se încarcă datele…</div>
      )}

      {selectedStoreId && stores.length > 0 && (
        <StoreInsightsCard
          scope={apiScope}
          store={stores.find((s) => s.storeId === selectedStoreId)?.name ?? ""}
          monthsWindow={monthsWindow}
        />
      )}

      {data && !loadingDashboard && (
        <>
          <KpiCards data={data} />
          <MonthlySection data={data} />
          <CategoriesSection data={data} />
          <BrandSplitSection data={data} />
        </>
      )}
    </div>
  );
}


// ── KPI cards ────────────────────────────────────────────────────────────


function KpiCards({ data }: { data: AMDDashboardResponse }) {
  const c = data.kpiCurr;
  const y = data.kpiYoy;
  const p = data.kpiPrev;

  const cards: KpiCardSpec[] = [
    {
      title: "Vânzări (curent)",
      curr: toNum(c.sales),
      yoy: toNum(y.sales),
      mom: toNum(p.sales),
      isMoney: true,
    },
    {
      title: "SKU-uri (curent)",
      curr: c.skuCount,
      yoy: y.skuCount,
      mom: p.skuCount,
      isMoney: false,
    },
    {
      title: "Cantitate (curent)",
      curr: toNum(c.quantity),
      yoy: toNum(y.quantity),
      mom: toNum(p.quantity),
      isMoney: false,
    },
  ];

  return (
    <section style={styles.section}>
      <h2 style={styles.sectionTitle}>KPI</h2>
      <div style={styles.kpiRow}>
        {cards.map((card) => (
          <KpiCard key={card.title} {...card} />
        ))}
      </div>
    </section>
  );
}

interface KpiCardSpec {
  title: string;
  curr: number;
  yoy: number;
  mom: number;
  isMoney: boolean;
}

function KpiCard({ title, curr, yoy, mom, isMoney }: KpiCardSpec) {
  const dYoy = pctDelta(curr, yoy);
  const dMom = pctDelta(curr, mom);
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiTitle}>{title}</div>
      <div style={styles.kpiValue}>
        {fmtRo(curr, isMoney ? 0 : 0)}{isMoney ? " RON" : ""}
      </div>
      <div style={styles.kpiDeltas}>
        <div>
          <span style={styles.kpiDeltaLabel}>vs. an precedent</span>
          <span style={{ ...styles.kpiDeltaValue, color: deltaColor(dYoy) }}>
            {fmtPct(dYoy)}
          </span>
          <span style={styles.kpiDeltaSub}>
            ({fmtRo(yoy, 0)}{isMoney ? " RON" : ""})
          </span>
        </div>
        <div>
          <span style={styles.kpiDeltaLabel}>vs. perioada anterioară</span>
          <span style={{ ...styles.kpiDeltaValue, color: deltaColor(dMom) }}>
            {fmtPct(dMom)}
          </span>
          <span style={styles.kpiDeltaSub}>
            ({fmtRo(mom, 0)}{isMoney ? " RON" : ""})
          </span>
        </div>
      </div>
    </div>
  );
}


// ── Monthly section ──────────────────────────────────────────────────────


function MonthlySection({ data }: { data: AMDDashboardResponse }) {
  const maxSales = useMemo<number>(() => {
    let max = 0;
    for (const m of data.monthly) {
      max = Math.max(max, toNum(m.salesCurr), toNum(m.salesPrevYear));
    }
    return max;
  }, [data]);

  const totals = useMemo(() => {
    let salesCurr = 0;
    let salesPrev = 0;
    for (const m of data.monthly) {
      salesCurr += toNum(m.salesCurr);
      salesPrev += toNum(m.salesPrevYear);
    }
    // SKU la nivel de perioadă = distinct peste fereastră, nu sumă lunară
    // (un SKU vândut în 3 luni ar fi numărat de 3 ori). Folosim KPI-ul.
    return {
      salesCurr,
      salesPrev,
      skuCurr: data.kpiCurr.skuCount,
      skuPrev: data.kpiYoy.skuCount,
    };
  }, [data]);

  return (
    <section style={styles.section}>
      <h2 style={styles.sectionTitle}>Evoluție lunară</h2>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.thLeft}>Lună</th>
            <th style={styles.thRight}>Vânzări curent</th>
            <th style={styles.thRight}>An precedent</th>
            <th style={styles.thRight}>Δ %</th>
            <th style={styles.thRight}>SKU curent</th>
            <th style={styles.thRight}>SKU an prec.</th>
            <th style={styles.thRight}>Δ SKU</th>
            <th style={styles.thLeft}>Bară</th>
          </tr>
        </thead>
        <tbody>
          {data.monthly.map((m) => {
            const sc = toNum(m.salesCurr);
            const sp = toNum(m.salesPrevYear);
            const dPct = pctDelta(sc, sp);
            const dSku = m.skuCurr - m.skuPrevYear;
            const wCurr = maxSales > 0 ? (sc / maxSales) * 100 : 0;
            const wPrev = maxSales > 0 ? (sp / maxSales) * 100 : 0;
            return (
              <tr key={`${m.year}-${m.month}`}>
                <td style={styles.tdLeft}>
                  {MONTH_NAMES[m.month] ?? m.month} {m.year}
                </td>
                <td style={styles.tdRight}>{fmtRo(sc, 0)}</td>
                <td style={styles.tdRight}>{fmtRo(sp, 0)}</td>
                <td style={{ ...styles.tdRight, color: deltaColor(dPct) }}>
                  {fmtPct(dPct)}
                </td>
                <td style={styles.tdRight}>{fmtRo(m.skuCurr, 0)}</td>
                <td style={styles.tdRight}>{fmtRo(m.skuPrevYear, 0)}</td>
                <td
                  style={{
                    ...styles.tdRight,
                    color: deltaColor(dSku === 0 ? 0 : dSku > 0 ? 1 : -1),
                  }}
                >
                  {dSku > 0 ? "+" : ""}{dSku}
                </td>
                <td style={styles.tdBar}>
                  <div style={styles.barTrack}>
                    <div
                      style={{
                        ...styles.barFillCurr,
                        width: `${wCurr}%`,
                      }}
                    />
                  </div>
                  <div style={styles.barTrack}>
                    <div
                      style={{
                        ...styles.barFillPrev,
                        width: `${wPrev}%`,
                      }}
                    />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          {(() => {
            const dPctTot = pctDelta(totals.salesCurr, totals.salesPrev);
            const dSkuTot = totals.skuCurr - totals.skuPrev;
            const totMax = Math.max(totals.salesCurr, totals.salesPrev);
            const wCurr = totMax > 0 ? (totals.salesCurr / totMax) * 100 : 0;
            const wPrev = totMax > 0 ? (totals.salesPrev / totMax) * 100 : 0;
            return (
              <tr>
                <td style={styles.tdFootLeft}>Total</td>
                <td style={styles.tdFootRight}>{fmtRo(totals.salesCurr, 0)}</td>
                <td style={styles.tdFootRight}>{fmtRo(totals.salesPrev, 0)}</td>
                <td style={{ ...styles.tdFootRight, color: deltaColor(dPctTot) }}>
                  {fmtPct(dPctTot)}
                </td>
                <td style={styles.tdFootRight}>{fmtRo(totals.skuCurr, 0)}</td>
                <td style={styles.tdFootRight}>{fmtRo(totals.skuPrev, 0)}</td>
                <td
                  style={{
                    ...styles.tdFootRight,
                    color: deltaColor(dSkuTot === 0 ? 0 : dSkuTot > 0 ? 1 : -1),
                  }}
                >
                  {dSkuTot > 0 ? "+" : ""}{dSkuTot}
                </td>
                <td style={styles.tdBar}>
                  <div style={styles.barTrack}>
                    <div
                      style={{
                        ...styles.barFillCurr,
                        width: `${wCurr}%`,
                      }}
                    />
                  </div>
                  <div style={styles.barTrack}>
                    <div
                      style={{
                        ...styles.barFillPrev,
                        width: `${wPrev}%`,
                      }}
                    />
                  </div>
                </td>
              </tr>
            );
          })()}
        </tfoot>
      </table>
      <div style={styles.legend}>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendSwatch, background: "#3b82f6" }} /> Curent
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendSwatch, background: "#94a3b8" }} /> An precedent
        </span>
      </div>
    </section>
  );
}


// ── Categories section ───────────────────────────────────────────────────


function CategoriesSection({ data }: { data: AMDDashboardResponse }) {
  const groupNoun = data.scope === "sika" ? "Target Market" : "Categorie";
  const sectionTitle = data.scope === "sika"
    ? "Pe Target Market"
    : "Pe categorie de produs";

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState<string>("");

  // Map category code → produsele acelei categorii (din data.products).
  const productsByCategory = useMemo(() => {
    const m = new Map<string, typeof data.products>();
    for (const p of data.products) {
      const key = p.categoryCode ?? p.categoryLabel ?? "—";
      const arr = m.get(key) ?? [];
      arr.push(p);
      m.set(key, arr);
    }
    return m;
  }, [data.products]);

  // Filtrare globală: dacă `search` e activ, păstrăm doar produsele cu match
  // (cod / nume / categorie) și auto-expandăm categoriile care au produse rămase.
  const filteredProductsByCategory = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return productsByCategory;
    const m = new Map<string, typeof data.products>();
    for (const [k, arr] of productsByCategory.entries()) {
      const matched = arr.filter((p) =>
        p.name.toLowerCase().includes(q)
        || p.code.toLowerCase().includes(q)
        || (p.categoryLabel ?? p.categoryCode ?? "").toLowerCase().includes(q)
      );
      if (matched.length > 0) m.set(k, matched);
    }
    return m;
  }, [productsByCategory, search, data.products]);

  const searchActive = search.trim().length > 0;

  function toggle(code: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
  }

  if (data.categories.length === 0) {
    return (
      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>{sectionTitle}</h2>
        <div style={styles.muted}>Nu există date pentru acest magazin.</div>
      </section>
    );
  }

  const totalCurr = data.categories.reduce(
    (sum, c) => sum + toNum(c.curr.sales),
    0,
  );
  const totalCurrAll = data.products.reduce(
    (s, p) => s + toNum(p.curr.sales),
    0,
  );

  // Când search e activ, ascundem categoriile fără produse match-uite.
  const visibleCategories = searchActive
    ? data.categories.filter((c) => filteredProductsByCategory.has(c.code))
    : data.categories;

  return (
    <section style={styles.section}>
      <div style={styles.productsHeader}>
        <h2 style={{ ...styles.sectionTitle, margin: 0 }}>{sectionTitle}</h2>
        <input
          type="search"
          placeholder="Caută cod / denumire / categorie…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-wide="true"
          style={styles.productsSearch}
        />
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={{ ...styles.thLeft, width: 28 }} aria-label="expand"></th>
              <th style={styles.thLeft}>{groupNoun}</th>
              <th style={styles.thRight}>Vânzări curent</th>
              <th style={styles.thRight}>% mix</th>
              <th style={styles.thRight}>An precedent</th>
              <th style={styles.thRight}>Δ %</th>
              <th style={styles.thRight}>SKU curent</th>
              <th style={styles.thRight}>SKU an prec.</th>
              <th style={styles.thRight}>Δ SKU</th>
            </tr>
          </thead>
          <tbody>
            {visibleCategories.length === 0 && (
              <tr>
                <td colSpan={9} style={{ ...styles.tdLeft, color: "#94a3b8" }}>
                  Nicio categorie nu corespunde căutării.
                </td>
              </tr>
            )}
            {visibleCategories.map((c) => {
              const sc = toNum(c.curr.sales);
              const sp = toNum(c.yoy.sales);
              const dPct = pctDelta(sc, sp);
              const mix = totalCurr > 0 ? (sc / totalCurr) * 100 : 0;
              const dSku = c.curr.skuCount - c.yoy.skuCount;
              const products = filteredProductsByCategory.get(c.code) ?? [];
              const isOpen = searchActive || expanded.has(c.code);
              const hasProducts = products.length > 0;
              return (
                <Fragment key={c.code}>
                  <tr
                    onClick={() => hasProducts && toggle(c.code)}
                    style={{
                      cursor: hasProducts ? "pointer" : "default",
                      background: isOpen ? "#f8fafc" : undefined,
                    }}
                  >
                    <td style={{ ...styles.tdLeft, textAlign: "center", color: "#64748b" }}>
                      {hasProducts ? (isOpen ? "▼" : "▶") : ""}
                    </td>
                    <td style={styles.tdLeft}>
                      <strong>{c.code}</strong>
                      {c.label !== c.code && (
                        <span style={styles.muted}> · {c.label}</span>
                      )}
                      {hasProducts && (
                        <span style={{ ...styles.muted, marginLeft: 8 }}>
                          ({products.length} produse)
                        </span>
                      )}
                    </td>
                    <td style={styles.tdRight}>{fmtRo(sc, 0)}</td>
                    <td style={styles.tdRight}>{mix.toFixed(1)}%</td>
                    <td style={styles.tdRight}>{fmtRo(sp, 0)}</td>
                    <td style={{ ...styles.tdRight, color: deltaColor(dPct) }}>
                      {fmtPct(dPct)}
                    </td>
                    <td style={styles.tdRight}>{c.curr.skuCount}</td>
                    <td style={styles.tdRight}>{c.yoy.skuCount}</td>
                    <td
                      style={{
                        ...styles.tdRight,
                        color: deltaColor(dSku === 0 ? 0 : dSku > 0 ? 1 : -1),
                      }}
                    >
                      {dSku > 0 ? "+" : ""}{dSku}
                    </td>
                  </tr>
                  {isOpen && hasProducts && (
                    <tr>
                      <td colSpan={9} style={styles.subTableCell}>
                        <table style={styles.subTable}>
                          <thead>
                            <tr>
                              <th style={styles.thLeft}>Produs</th>
                              <th style={styles.thRight}>Cantitate</th>
                              <th style={styles.thRight}>Vânzări curent</th>
                              <th style={styles.thRight}>% mix</th>
                              <th style={styles.thRight}>An precedent</th>
                              <th style={styles.thRight}>Δ %</th>
                            </tr>
                          </thead>
                          <tbody>
                            {products.map((p) => {
                              const psc = toNum(p.curr.sales);
                              const psp = toNum(p.yoy.sales);
                              const pqc = toNum(p.curr.quantity);
                              const pdPct = pctDelta(psc, psp);
                              const pmix = totalCurrAll > 0 ? (psc / totalCurrAll) * 100 : 0;
                              return (
                                <tr key={p.productId}>
                                  <td style={styles.tdLeft}>
                                    <div style={{ fontWeight: 600 }}>{p.name}</div>
                                    <div style={{ fontSize: 11, color: "#94a3b8" }}>{p.code}</div>
                                  </td>
                                  <td style={styles.tdRight}>{fmtRo(pqc, 1)}</td>
                                  <td style={styles.tdRight}>{fmtRo(psc, 0)}</td>
                                  <td style={styles.tdRight}>{pmix.toFixed(1)}%</td>
                                  <td style={styles.tdRight}>{fmtRo(psp, 0)}</td>
                                  <td style={{ ...styles.tdRight, color: deltaColor(pdPct) }}>
                                    {fmtPct(pdPct)}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}


// ── Brand vs Private Label ──────────────────────────────────────────────


function BrandSplitSection({ data }: { data: AMDDashboardResponse }) {
  const b = data.brandSplit.brand;
  const pl = data.brandSplit.privateLabel;
  const bY = data.brandSplit.brandYoy;
  const plY = data.brandSplit.privateLabelYoy;

  const total = toNum(b.sales) + toNum(pl.sales);

  function row(label: string, m: AMDMetrics, mY: AMDMetrics, color: string) {
    const sc = toNum(m.sales);
    const sp = toNum(mY.sales);
    const dPct = pctDelta(sc, sp);
    const mix = total > 0 ? (sc / total) * 100 : 0;
    return (
      <tr>
        <td style={styles.tdLeft}>
          <span style={{ ...styles.dot, background: color }} /> {label}
        </td>
        <td style={styles.tdRight}>{fmtRo(sc, 0)}</td>
        <td style={styles.tdRight}>{mix.toFixed(1)}%</td>
        <td style={styles.tdRight}>{fmtRo(sp, 0)}</td>
        <td style={{ ...styles.tdRight, color: deltaColor(dPct) }}>
          {fmtPct(dPct)}
        </td>
        <td style={styles.tdRight}>{m.skuCount}</td>
        <td style={styles.tdRight}>{mY.skuCount}</td>
      </tr>
    );
  }

  return (
    <section style={styles.section}>
      <h2 style={styles.sectionTitle}>Brand vs Marcă Privată</h2>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.thLeft}>Tip</th>
            <th style={styles.thRight}>Vânzări curent</th>
            <th style={styles.thRight}>% mix</th>
            <th style={styles.thRight}>An precedent</th>
            <th style={styles.thRight}>Δ %</th>
            <th style={styles.thRight}>SKU curent</th>
            <th style={styles.thRight}>SKU an prec.</th>
          </tr>
        </thead>
        <tbody>
          {row("Brand", b, bY, "#3b82f6")}
          {row("Marcă Privată", pl, plY, "#f59e0b")}
        </tbody>
      </table>
    </section>
  );
}


// ── Styles ───────────────────────────────────────────────────────────────


const styles: Record<string, CSSProperties> = {
  page: {
    padding: 24,
    maxWidth: 1400,
    margin: "0 auto",
    fontFamily: "system-ui, -apple-system, sans-serif",
  },
  headerRow: {
    display: "flex",
    alignItems: "baseline",
    gap: 16,
    flexWrap: "wrap",
    marginBottom: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: 600,
    margin: 0,
    color: "#0f172a",
  },
  subtitle: {
    display: "inline-flex",
    alignItems: "baseline",
    gap: 8,
    flexWrap: "wrap",
  },
  storeNameBig: {
    fontSize: 20,
    fontWeight: 700,
    color: "#0f172a",
    letterSpacing: 0.2,
  },
  subtitleMeta: {
    color: "#64748b",
    fontSize: 13,
    fontWeight: 500,
  },
  controls: {
    display: "flex",
    gap: 16,
    flexWrap: "wrap",
    marginBottom: 16,
    alignItems: "flex-end",
  },
  controlBlock: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    minWidth: 140,
  },
  controlLabel: {
    fontSize: 12,
    color: "#64748b",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  btnGroup: {
    display: "inline-flex",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    overflow: "hidden",
  },
  monthBtn: {
    padding: "6px 12px",
    background: "#fff",
    border: "none",
    borderRight: "1px solid #cbd5e1",
    cursor: "pointer",
    fontSize: 14,
    color: "#334155",
  },
  monthBtnActive: {
    background: "#3b82f6",
    color: "#fff",
  },
  select: {
    padding: "6px 10px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    background: "#fff",
    fontSize: 14,
    minWidth: 160,
  },
  selectWide: {
    padding: "10px 14px",
    border: "1px solid #cbd5e1",
    borderRadius: 8,
    background: "#fff",
    fontSize: 16,
    fontWeight: 600,
    color: "#0f172a",
    width: "100%",
    minHeight: 42,
  },
  error: {
    padding: 12,
    background: "#fee2e2",
    color: "#991b1b",
    border: "1px solid #fecaca",
    borderRadius: 6,
    marginBottom: 12,
  },
  loading: {
    padding: 12,
    color: "#64748b",
    fontStyle: "italic",
  },
  section: {
    marginTop: 24,
    padding: 16,
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 600,
    margin: "0 0 12px",
    color: "#0f172a",
  },
  productsHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
    marginBottom: 12,
  },
  productsSearch: {
    padding: "8px 12px",
    border: "1px solid #cbd5e1",
    borderRadius: 6,
    fontSize: 13,
    minWidth: 260,
    flex: "1 1 260px",
    maxWidth: 420,
  },
  subTableCell: {
    padding: "0 0 0 28px",
    background: "#f8fafc",
    borderBottom: "1px solid #f1f5f9",
  },
  subTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 12,
    background: "#fff",
    border: "1px solid #e2e8f0",
    borderRadius: 6,
    margin: "8px 8px 8px 0",
  },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: 12,
  },
  kpiCard: {
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: 14,
    background: "#f8fafc",
  },
  kpiTitle: {
    fontSize: 12,
    color: "#64748b",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    marginBottom: 6,
  },
  kpiValue: {
    fontSize: 24,
    fontWeight: 700,
    color: "#0f172a",
    marginBottom: 8,
  },
  kpiDeltas: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    fontSize: 13,
  },
  kpiDeltaLabel: {
    color: "#64748b",
    marginRight: 6,
  },
  kpiDeltaValue: {
    fontWeight: 600,
    marginRight: 4,
  },
  kpiDeltaSub: {
    color: "#94a3b8",
    fontSize: 12,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
  },
  thLeft: {
    textAlign: "left",
    padding: "8px 10px",
    borderBottom: "2px solid #e2e8f0",
    color: "#475569",
    fontWeight: 600,
    background: "#f8fafc",
  },
  thRight: {
    textAlign: "right",
    padding: "8px 10px",
    borderBottom: "2px solid #e2e8f0",
    color: "#475569",
    fontWeight: 600,
    background: "#f8fafc",
  },
  tdLeft: {
    textAlign: "left",
    padding: "8px 10px",
    borderBottom: "1px solid #f1f5f9",
    color: "#0f172a",
  },
  tdRight: {
    textAlign: "right",
    padding: "8px 10px",
    borderBottom: "1px solid #f1f5f9",
    color: "#0f172a",
    fontVariantNumeric: "tabular-nums",
  },
  tdBar: {
    width: 160,
    padding: "8px 10px",
    borderBottom: "1px solid #f1f5f9",
  },
  tdFootLeft: {
    textAlign: "left",
    padding: "10px",
    borderTop: "2px solid #cbd5e1",
    color: "#0f172a",
    fontWeight: 700,
    background: "#f1f5f9",
  },
  tdFootRight: {
    textAlign: "right",
    padding: "10px",
    borderTop: "2px solid #cbd5e1",
    color: "#0f172a",
    fontWeight: 700,
    fontVariantNumeric: "tabular-nums",
    background: "#f1f5f9",
  },
  barTrack: {
    height: 6,
    background: "#f1f5f9",
    borderRadius: 3,
    overflow: "hidden",
    marginBottom: 2,
  },
  barFillCurr: {
    height: "100%",
    background: "#3b82f6",
  },
  barFillPrev: {
    height: "100%",
    background: "#94a3b8",
  },
  legend: {
    display: "flex",
    gap: 16,
    marginTop: 8,
    fontSize: 12,
    color: "#64748b",
  },
  legendItem: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  },
  legendSwatch: {
    display: "inline-block",
    width: 12,
    height: 12,
    borderRadius: 2,
  },
  muted: {
    color: "#94a3b8",
    fontSize: 12,
  },
  dot: {
    display: "inline-block",
    width: 10,
    height: 10,
    borderRadius: "50%",
    marginRight: 6,
    verticalAlign: "middle",
  },
};
