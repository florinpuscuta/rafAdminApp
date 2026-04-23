import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../../shared/api";
import { CollapsibleBlock } from "../../shared/ui/CollapsibleBlock";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { groupByEpsSubgroup, isEpsCategory } from "../../shared/utils/epsSubgroup";
import { downloadTableAsCsv } from "../../shared/utils/exportCsv";
import { sikaTm } from "../../shared/utils/sikaTm";
import {
  getPret3Net,
  loadDiscounts,
  netFactor,
  saveDiscounts,
} from "./api";
import type {
  Discount,
  DiscountConfig,
  Pret3NetFilters,
  Pret3NetProduct,
  Pret3NetResponse,
} from "./types";

const MONTHS = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

const KA_LABELS: Record<string, string> = {
  DEDEMAN: "Dedeman", LEROY: "Leroy Merlin", HORNBACH: "Hornbach",
  ALTEX: "Altex",
};
const KA_COLORS: Record<string, string> = {
  DEDEMAN: "#22c55e", LEROY: "#3b82f6", HORNBACH: "#f59e0b",
  ALTEX: "#ef4444",
};

// Categoriile unde NU se aplică discount (legacy comportament pt EPS).
const NO_DISCOUNT_CATS = new Set(["EPS"]);

function fmtFull(v: string | number | null | undefined): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

function fmtPrice(v: number | null): string {
  if (v == null) return "—";
  if (!Number.isFinite(v)) return "—";
  return v.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function Pret3NetPage() {
  const { scope } = useCompanyScope();
  const company = scope === "sika" ? "sika" : scope === "sikadp" ? "sikadp" : "adeplast";
  const toast = useToast();
  const [data, setData] = useState<Pret3NetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Pret3NetFilters>({ year: CURRENT_YEAR, company });
  const [discounts, setDiscounts] = useState<DiscountConfig>(() => loadDiscounts());
  const [activeCategory, setActiveCategory] = useState<string>("ALL");
  const tableRef = useRef<HTMLTableElement>(null);

  const load = useCallback(async (f: Pret3NetFilters) => {
    setLoading(true);
    try {
      setData(await getPret3Net(f));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setFilters((prev) => ({ ...prev, company }));
  }, [company]);

  useEffect(() => { load(filters); }, [filters, load]);

  const kaClients = data?.kaClients ?? [];

  // Factor net per KA (aplicat compus).
  const kaNet = useMemo(() => {
    const out: Record<string, number> = {};
    for (const k of kaClients) out[k] = netFactor(discounts[k]);
    return out;
  }, [discounts, kaClients]);

  function update(patch: Partial<Pret3NetFilters>) {
    const next = { ...filters, ...patch };
    (Object.keys(next) as (keyof Pret3NetFilters)[]).forEach((k) => {
      const v = next[k];
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
        delete next[k];
      }
    });
    setFilters(next);
  }

  function addDiscount(ka: string) {
    const next = { ...discounts, [ka]: [...(discounts[ka] ?? []), { name: "", pct: 0 } as Discount] };
    setDiscounts(next);
  }

  function removeDiscount(ka: string, idx: number) {
    const list = [...(discounts[ka] ?? [])];
    list.splice(idx, 1);
    const next = { ...discounts, [ka]: list };
    setDiscounts(next);
  }

  function updateDiscount(ka: string, idx: number, patch: Partial<Discount>) {
    const list = [...(discounts[ka] ?? [])];
    list[idx] = { ...list[idx], ...patch };
    const next = { ...discounts, [ka]: list };
    setDiscounts(next);
  }

  function persistDiscounts() {
    saveDiscounts(discounts);
    toast.success("Discounturi salvate local");
  }

  const isSika = scope === "sika";

  // La Sika regrupăm produsele pe TM (Target Market) — ignorăm category_code.
  // La Adeplast păstrăm categoriile din backend.
  const categoriesByTm = useMemo<Record<string, Pret3NetProduct[]>>(() => {
    if (!data) return {};
    if (!isSika) return data.categories;
    const out: Record<string, Pret3NetProduct[]> = {};
    for (const prods of Object.values(data.categories)) {
      for (const p of prods) {
        const tm = sikaTm(p.description);
        if (!out[tm]) out[tm] = [];
        out[tm].push(p);
      }
    }
    return out;
  }, [data, isSika]);

  const orderedCats = useMemo(() => {
    return Object.keys(categoriesByTm).sort((a, b) => {
      const sa = (categoriesByTm[a] || []).reduce((s, p) => s + Number(p.totalSales || 0), 0);
      const sb = (categoriesByTm[b] || []).reduce((s, p) => s + Number(p.totalSales || 0), 0);
      return sb - sa;
    });
  }, [categoriesByTm]);

  const visibleCats = useMemo(() => {
    if (activeCategory === "ALL") return orderedCats;
    return orderedCats.filter((c) => c === activeCategory);
  }, [activeCategory, orderedCats]);

  return (
    <div style={{
      padding: "4px 4px 20px", color: "var(--text)",
      zoom: 0.80 as unknown as number,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          💰 Preț 3 Net Comp KA
        </h2>
        <button
          type="button"
          data-compact="true"
          onClick={() => downloadTableAsCsv(tableRef.current, "pret-3-net-comp-ka.csv")}
          style={{
            marginLeft: "auto", padding: "6px 10px", fontSize: 12, fontWeight: 600,
            background: "#16a34a", color: "#fff", border: "none",
            borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap", minHeight: 34,
          }}
          title="Descarcă tabelul ca Excel"
        >
          ⬇ Excel
        </button>
      </div>
      <p style={{ color: "var(--fg-muted, #666)", fontSize: 14, marginTop: 0 }}>
        Preț mediu de facturare pe produs × KA (valoare / cantitate), cu back-discount
        contractual aplicat. Discounturile sunt salvate local (per browser).
      </p>

      <div style={styles.filterBar}>
        <label style={styles.label}>
          An
          <select
            value={filters.year ?? ""}
            onChange={(e) => update({ year: e.target.value ? Number(e.target.value) : undefined })}
            style={styles.select}
          >
            <option value="">toate</option>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <label style={styles.label}>
          Lună
          <select
            value={(filters.months && filters.months[0]) ?? ""}
            onChange={(e) => update({
              months: e.target.value ? [Number(e.target.value)] : undefined,
            })}
            style={styles.select}
            disabled={!filters.year}
          >
            <option value="">toate</option>
            {MONTHS.map((name, i) => (
              <option key={i + 1} value={i + 1}>{name}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Discount config area */}
      <div style={styles.discountBlock}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <b style={{ fontSize: 13 }}>Back-Discount Contractual per KA</b>
          <button onClick={persistDiscounts} style={styles.saveBtn}>Salvează local</button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.max(kaClients.length, 1)}, 1fr)`, gap: 12 }}>
          {kaClients.map((k) => {
            const discs = discounts[k] ?? [];
            const totalPct = (1 - netFactor(discs)) * 100;
            return (
              <div key={k} style={{ ...styles.discountCard, borderColor: `${KA_COLORS[k]}33` }}>
                <div style={{ fontWeight: 700, fontSize: 12, color: KA_COLORS[k], marginBottom: 6 }}>
                  {KA_LABELS[k] ?? k}
                  <span style={{ float: "right", fontSize: 11, color: "var(--fg-muted, #888)" }}>
                    {totalPct > 0 ? `-${totalPct.toFixed(2)}%` : "fără discount"}
                  </span>
                </div>
                {discs.map((d, i) => (
                  <div key={i} style={{ display: "flex", gap: 4, marginBottom: 4 }}>
                    <input
                      type="text"
                      placeholder="nume"
                      value={d.name}
                      onChange={(e) => updateDiscount(k, i, { name: e.target.value })}
                      style={{ ...styles.input, flex: 1, fontSize: 11 }}
                    />
                    <input
                      type="number"
                      placeholder="%"
                      value={d.pct}
                      onChange={(e) => updateDiscount(k, i, { pct: Number(e.target.value) || 0 })}
                      style={{ ...styles.input, width: 60, fontSize: 11 }}
                      step="0.01"
                    />
                    <button onClick={() => removeDiscount(k, i)} style={styles.delBtn}>×</button>
                  </div>
                ))}
                <button onClick={() => addDiscount(k)} style={styles.addDiscBtn}>+ discount</button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Category tabs */}
      {orderedCats.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 12, flexWrap: "wrap" }}>
          <button
            onClick={() => setActiveCategory("ALL")}
            style={tabStyle(activeCategory === "ALL")}
          >
            Toate ({orderedCats.length})
          </button>
          {orderedCats.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              style={tabStyle(activeCategory === cat)}
            >
              {cat} ({(categoriesByTm[cat] || []).length})
            </button>
          ))}
        </div>
      )}

      {loading && !data ? (
        <TableSkeleton rows={10} cols={kaClients.length * 2 + 2} />
      ) : scope === "adeplast" ? (
        <>
          {renderBrandSection(visibleCats, categoriesByTm, false, "Adeplast")}
          {renderBrandSection(visibleCats, categoriesByTm, true, "Marcă privată")}
        </>
      ) : (
        renderBrandSection(visibleCats, categoriesByTm, null)
      )}
    </div>
  );

  function renderBrandSection(
    cats: string[],
    catsByTm: Record<string, Pret3NetProduct[]>,
    plFilter: boolean | null,
    brandLabel?: string,
  ) {
    const filtered: [string, Pret3NetProduct[]][] = cats
      .map((cat): [string, Pret3NetProduct[]] => {
        const all = catsByTm[cat] || [];
        if (plFilter === null) return [cat, all];
        return [cat, all.filter((p) => !!p.isPrivateLabel === plFilter)];
      })
      .filter(([, prods]) => prods.length > 0);

    if (filtered.length === 0) return null;

    const totalProds = filtered.reduce((s, [, p]) => s + p.length, 0);
    const body = filtered.map(([cat, prods], idx) => renderCategoryBlock(cat, prods, idx));

    if (brandLabel) {
      return (
        <div style={{ marginBottom: 14 }}>
          <CollapsibleBlock title={brandLabel} subtitle={`${totalProds} produse`}>
            {body}
          </CollapsibleBlock>
        </div>
      );
    }
    return <>{body}</>;
  }

  function renderCategoryBlock(cat: string, prods: Pret3NetProduct[], idx: number) {
    const applyDiscount = !NO_DISCOUNT_CATS.has(cat.toUpperCase());
    // La Sika categoria e un TM → fără EPS subgroups.
    const isEps = !isSika && isEpsCategory(cat);
    const epsGroups = isEps
      ? groupByEpsSubgroup(prods, (p) => p.description, (p) => p.totalSales)
      : null;

    const renderRow = (p: typeof prods[number], i: number) => (
      <tr key={`${p.description}-${i}`}>
        <td style={td}>{p.description}</td>
        {kaClients.map((k) => {
          const c = p.clients[k];
          const raw = c?.price != null ? Number(c.price) : null;
          const net = raw != null && applyDiscount ? raw * kaNet[k] : raw;
          return (
            <td key={k} style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
              {fmtPrice(net)}
              {applyDiscount && raw != null && kaNet[k] < 1 && (
                <div style={{ fontSize: 10, color: "var(--fg-muted, #aaa)" }}>
                  brut {fmtPrice(raw)}
                </div>
              )}
            </td>
          );
        })}
        <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
          {fmtFull(p.totalSales)}
        </td>
      </tr>
    );

    const headerRow = (
      <tr>
        <th style={th}>Produs</th>
        {kaClients.map((k) => (
          <th key={k} style={{ ...th, textAlign: "right", color: KA_COLORS[k] }}>
            {KA_LABELS[k] ?? k}
          </th>
        ))}
        <th style={{ ...th, textAlign: "right" }}>Vânzări</th>
      </tr>
    );

    return (
      <div key={cat} style={styles.catBlock}>
        <CollapsibleBlock
          title={cat}
          subtitle={`(${prods.length} produse)`}
        >
          {isEps && epsGroups ? (
            epsGroups.map((g, gi) => (
              <div key={g.key} style={styles.subBlock}>
                <CollapsibleBlock
                  title={g.label}
                  subtitle={`${g.products.length} produse · ${fmtFull(g.totalSales)}`}
                  level={1}
                >
                  <div style={{ overflowX: "auto" }}>
                    <table ref={idx === 0 && gi === 0 ? tableRef : undefined} style={styles.table}>
                      <thead>{headerRow}</thead>
                      <tbody>{g.products.map(renderRow)}</tbody>
                    </table>
                  </div>
                </CollapsibleBlock>
              </div>
            ))
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table ref={idx === 0 ? tableRef : undefined} style={styles.table}>
                <thead>{headerRow}</thead>
                <tbody>{prods.map(renderRow)}</tbody>
              </table>
            </div>
          )}
        </CollapsibleBlock>
      </div>
    );
  }
}

function tabStyle(active: boolean): React.CSSProperties {
  return {
    padding: "6px 14px",
    borderRadius: 6,
    border: `1px solid ${active ? "#2563eb" : "var(--border, #ccc)"}`,
    background: active ? "#2563eb" : "transparent",
    color: active ? "#fff" : "var(--fg, #333)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  };
}

const styles: Record<string, React.CSSProperties> = {
  filterBar: {
    display: "flex", gap: 12, padding: "10px 12px",
    background: "var(--bg-elevated, #fafafa)",
    border: "1px solid var(--border, #eee)", borderRadius: 6,
    marginBottom: 16, flexWrap: "wrap", alignItems: "flex-end",
  },
  label: { display: "flex", flexDirection: "column", gap: 3, fontSize: 12, color: "var(--fg-muted, #666)" },
  select: { padding: 6, fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4 },
  input: { padding: "5px 8px", fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4 },
  discountBlock: {
    background: "var(--bg-elevated, #fafafa)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    padding: 12,
    marginBottom: 16,
  },
  discountCard: {
    background: "var(--bg, #fff)",
    borderRadius: 6,
    padding: 8,
    border: "1px solid var(--border, #eee)",
  },
  saveBtn: {
    padding: "4px 10px", fontSize: 12, cursor: "pointer",
    background: "#16a34a", color: "#fff", border: "none", borderRadius: 4,
  },
  addDiscBtn: {
    marginTop: 4, width: "100%",
    padding: "3px 8px", fontSize: 11, cursor: "pointer",
    background: "transparent", color: "var(--fg-muted, #666)",
    border: "1px dashed var(--border, #ccc)", borderRadius: 4,
  },
  delBtn: {
    padding: "0 6px", fontSize: 13, cursor: "pointer",
    background: "transparent", color: "#dc2626",
    border: "1px solid var(--border, #ccc)", borderRadius: 4,
  },
  catBlock: {
    background: "var(--bg-elevated, #fff)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    padding: 12,
    marginBottom: 12,
  },
  subBlock: {
    background: "var(--bg, #fafafa)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 4,
    padding: 8,
    marginBottom: 8,
  },
  table: { borderCollapse: "collapse", width: "100%" },
};
const th: React.CSSProperties = {
  textAlign: "left", padding: "8px 12px",
  borderBottom: "2px solid var(--border, #333)", fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px", borderBottom: "1px solid var(--border, #eee)", fontSize: 13,
};
