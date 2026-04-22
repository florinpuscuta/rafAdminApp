import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../../shared/api";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { downloadTableAsCsv } from "../../shared/utils/exportCsv";
import { getKaRetail } from "./api";
import type { KaRetailFilters, KaRetailResponse, KaRetailRow } from "./types";

const MONTHS = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

function fmtFull(v: string | number | null | undefined): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

function fmtPrice(v: string | null): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(v: string | null): string {
  if (v == null) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function diffColor(v: string | null): string {
  if (v == null) return "var(--fg-muted, #666)";
  const n = Number(v);
  if (n > 5) return "#15803d";
  if (n < -5) return "#dc2626";
  return "var(--fg-muted, #666)";
}

export default function PreturiKaRetailPage() {
  const toast = useToast();
  const [data, setData] = useState<KaRetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<KaRetailFilters>({ year: CURRENT_YEAR, limit: 15 });
  const [search, setSearch] = useState("");
  const tableRef = useRef<HTMLTableElement>(null);

  const load = useCallback(async (f: KaRetailFilters) => {
    setLoading(true);
    try {
      setData(await getKaRetail(f));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(filters); }, [filters, load]);

  const filteredRows = useMemo(() => {
    if (!data) return [];
    const q = norm(search);
    if (!q) return data.rows;
    return data.rows.filter((r) =>
      norm(`${r.description} ${r.productCode ?? ""} ${r.category ?? ""}`).includes(q),
    );
  }, [data, search]);

  function update(patch: Partial<KaRetailFilters>) {
    const next = { ...filters, ...patch };
    (Object.keys(next) as (keyof KaRetailFilters)[]).forEach((k) => {
      const v = next[k];
      if (v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) {
        delete next[k];
      }
    });
    setFilters(next);
  }

  return (
    <div style={{
      padding: "4px 4px 20px", color: "var(--text)",
      zoom: 0.80 as unknown as number,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          🏪 Prețuri KA vs Retail
        </h2>
        <button
          type="button"
          data-compact="true"
          onClick={() => downloadTableAsCsv(tableRef.current, "preturi-ka-vs-retail.csv")}
          style={{
            marginLeft: "auto",
            padding: "6px 10px", fontSize: 12, fontWeight: 600,
            background: "#16a34a", color: "#fff",
            border: "none", borderRadius: 6, cursor: "pointer",
            whiteSpace: "nowrap", minHeight: 34,
          }}
          title="Descarcă tabelul ca Excel (CSV cu ; separator, UTF-8)"
        >
          ⬇ Excel
        </button>
      </div>
      <p style={{ color: "var(--fg-muted, #666)", fontSize: 14, marginTop: 0 }}>
        Top produse vândute și pe KA și pe Retail, cu preț mediu pe fiecare canal
        și diferența procentuală. Calculat ca <code>SUM(amount) / SUM(quantity)</code>.
        Include doar produsele vândute în <b>ambele canale</b>.
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
        <label style={styles.label}>
          Categorie
          <input
            type="text"
            placeholder="ex: ADEZIVI"
            value={filters.category ?? ""}
            onChange={(e) => update({ category: e.target.value || undefined })}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Top N
          <input
            type="number"
            min={1}
            max={200}
            step={1}
            value={filters.limit ?? 15}
            onChange={(e) => update({ limit: Number(e.target.value) || 15 })}
            style={{ ...styles.input, width: 80 }}
          />
        </label>
      </div>

      {data && data.rows.length > 0 && (
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Caută produs…"
          total={data.rows.length}
          visible={filteredRows.length}
        />
      )}

      {loading && !data ? (
        <TableSkeleton rows={10} cols={9} />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table ref={tableRef} style={styles.table}>
            <thead>
              <tr>
                <th style={th}>#</th>
                <th style={th}>Produs</th>
                <th style={{ ...th, textAlign: "right", color: "#2563eb" }}>Cant. KA</th>
                <th style={{ ...th, textAlign: "right", color: "#2563eb" }}>Preț mediu KA</th>
                <th style={{ ...th, textAlign: "right", color: "#f97316" }}>Cant. Retail</th>
                <th style={{ ...th, textAlign: "right", color: "#f97316" }}>Preț mediu Retail</th>
                <th style={{ ...th, textAlign: "right" }}>Diferență %</th>
              </tr>
            </thead>
            <tbody>
              {!data || data.rows.length === 0 ? (
                <tr><td colSpan={7} style={td}>
                  Niciun produs vândut în ambele canale (KA + Retail) în perioada selectată.
                </td></tr>
              ) : filteredRows.length === 0 ? (
                <tr><td colSpan={7} style={td}>Niciun rezultat pentru „{search}".</td></tr>
              ) : (
                filteredRows.map((r, i) => <Row key={`${r.description}-${i}`} r={r} idx={i + 1} />)
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Row({ r, idx }: { r: KaRetailRow; idx: number }) {
  return (
    <tr>
      <td style={{ ...td, color: "var(--fg-muted, #888)" }}>{idx}</td>
      <td style={td} title={r.description}>
        {r.description}
        {r.productCode && <span style={{ marginLeft: 6, fontSize: 11, color: "var(--fg-muted, #888)" }}><code>{r.productCode}</code></span>}
      </td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmtFull(r.kaQty)}</td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "#2563eb" }}>
        {fmtPrice(r.kaPrice)}
      </td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmtFull(r.retailQty)}</td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "#f97316" }}>
        {fmtPrice(r.retailPrice)}
      </td>
      <td style={{
        ...td, textAlign: "right", fontVariantNumeric: "tabular-nums",
        color: diffColor(r.diffPct), fontWeight: 600,
      }}>
        {fmtPct(r.diffPct)}
      </td>
    </tr>
  );
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
  table: { borderCollapse: "collapse", width: "100%" },
};
const th: React.CSSProperties = {
  textAlign: "left", padding: "8px 12px",
  borderBottom: "2px solid var(--border, #333)", fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px", borderBottom: "1px solid var(--border, #eee)", fontSize: 13,
};
