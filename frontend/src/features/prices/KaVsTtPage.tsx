import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  downloadKaVsTtCsv,
  getKaVsTt,
  type KaVsTtFilters,
  type KaVsTtResponse,
  type KaVsTtRow,
} from "./api";

function fmtPrice(val: string | null): string {
  if (val == null) return "—";
  const n = Number(val);
  return n.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(val: string | null): string {
  if (val == null) return "—";
  const n = Number(val);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function deltaColor(deltaPct: string | null): string {
  if (deltaPct == null) return "var(--fg-muted, #666)";
  const n = Number(deltaPct);
  if (n > 5) return "#15803d";  // KA mult mai scump = verde (bine pt marjă)
  if (n < -5) return "#dc2626"; // KA mult mai ieftin = roșu (posibil presiune de discount)
  return "var(--fg-muted, #666)";
}

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];
const MONTHS = [
  "ian", "feb", "mar", "apr", "mai", "iun",
  "iul", "aug", "sep", "oct", "nov", "dec",
];

export default function KaVsTtPage() {
  const toast = useToast();
  const [data, setData] = useState<KaVsTtResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState<KaVsTtFilters>({ minQty: 10 });
  const [search, setSearch] = useState("");

  const load = useCallback(async (f: KaVsTtFilters) => {
    setLoading(true);
    try {
      setData(await getKaVsTt(f));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load(filters);
  }, [filters, load]);

  const filteredRows = useMemo(() => {
    if (!data) return [];
    const q = norm(search);
    if (!q) return data.rows;
    return data.rows.filter((r) =>
      norm(`${r.description} ${r.productCode ?? ""} ${r.category ?? ""}`).includes(q),
    );
  }, [data, search]);

  async function handleExport() {
    setExporting(true);
    try {
      await downloadKaVsTtCsv(filters);
      toast.success("Export pornit");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Export eșuat");
    } finally {
      setExporting(false);
    }
  }

  function update(patch: Partial<KaVsTtFilters>) {
    const next = { ...filters, ...patch };
    (Object.keys(next) as (keyof KaVsTtFilters)[]).forEach((k) => {
      if (next[k] === undefined || next[k] === "" || Number.isNaN(next[k] as number)) {
        delete next[k];
      }
    });
    setFilters(next);
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Prețuri KA vs TT</h2>
      <p style={{ color: "var(--fg-muted, #666)", fontSize: 14, marginTop: 0 }}>
        Preț mediu Adeplast per produs, comparat între Key Accounts și Traditional Trade.
        Delta pozitiv = KA mai scump decât TT. Calculat ca <code>SUM(amount) / SUM(quantity)</code>
        pe fiecare canal.
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
            value={filters.month ?? ""}
            onChange={(e) => update({ month: e.target.value ? Number(e.target.value) : undefined })}
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
            placeholder="ex: Adezivi"
            value={filters.category ?? ""}
            onChange={(e) => update({ category: e.target.value || undefined })}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Prag cant. min
          <input
            type="number"
            min={0}
            step={1}
            value={filters.minQty ?? 10}
            onChange={(e) => update({ minQty: Number(e.target.value) || 0 })}
            style={{ ...styles.input, width: 80 }}
            title="Exclude produsele cu volum mic unde media e nereprezentativă"
          />
        </label>
        <button onClick={handleExport} disabled={exporting} style={styles.exportBtn}>
          {exporting ? "Exportă…" : "Export CSV"}
        </button>
      </div>

      {data?.summary && (
        <div style={styles.summaryRow}>
          <div style={styles.summaryCard}>
            <div style={styles.summaryLabel}>Preț mediu KA</div>
            <div style={styles.summaryVal}>{fmtPrice(data.summary.kaAvgPrice)} RON</div>
          </div>
          <div style={styles.summaryCard}>
            <div style={styles.summaryLabel}>Preț mediu TT</div>
            <div style={styles.summaryVal}>{fmtPrice(data.summary.ttAvgPrice)} RON</div>
          </div>
          <div style={styles.summaryCard}>
            <div style={styles.summaryLabel}>Diferență (KA − TT)</div>
            <div style={{ ...styles.summaryVal, color: deltaColor(data.summary.deltaPct) }}>
              {fmtPct(data.summary.deltaPct)}
            </div>
          </div>
        </div>
      )}

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
        <TableSkeleton rows={8} cols={8} />
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>Produs</th>
              <th style={th}>Cod</th>
              <th style={th}>Categorie</th>
              <th style={{ ...th, textAlign: "right" }}>Preț KA</th>
              <th style={{ ...th, textAlign: "right" }}>Preț TT</th>
              <th style={{ ...th, textAlign: "right" }}>Δ abs</th>
              <th style={{ ...th, textAlign: "right" }}>Δ %</th>
              <th style={{ ...th, textAlign: "right" }}>Cant. KA / TT</th>
            </tr>
          </thead>
          <tbody>
            {!data || data.rows.length === 0 ? (
              <tr><td colSpan={8} style={td}>
                Niciun produs vândut în ambele canale cu cantitate ≥ {filters.minQty ?? 0}.
                Încearcă să scazi pragul sau să schimbi filtrul de perioadă.
              </td></tr>
            ) : filteredRows.length === 0 ? (
              <tr><td colSpan={8} style={td}>Niciun rezultat pentru „{search}".</td></tr>
            ) : (
              filteredRows.map((r, i) => <Row key={`${r.description}-${i}`} r={r} />)
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Row({ r }: { r: KaVsTtRow }) {
  return (
    <tr>
      <td style={td}>{r.description}</td>
      <td style={td}>{r.productCode ? <code>{r.productCode}</code> : "—"}</td>
      <td style={td}>{r.category ?? "—"}</td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {fmtPrice(r.kaPrice)}
      </td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {fmtPrice(r.ttPrice)}
      </td>
      <td style={{ ...td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
        {fmtPrice(r.deltaAbs)}
      </td>
      <td style={{
        ...td, textAlign: "right", fontVariantNumeric: "tabular-nums",
        color: deltaColor(r.deltaPct), fontWeight: 500,
      }}>
        {fmtPct(r.deltaPct)}
      </td>
      <td style={{ ...td, textAlign: "right", fontSize: 11, color: "var(--fg-muted, #888)" }}>
        {Number(r.kaQty).toFixed(0)} / {Number(r.ttQty).toFixed(0)}
      </td>
    </tr>
  );
}

const styles: Record<string, React.CSSProperties> = {
  filterBar: {
    display: "flex",
    gap: 12,
    padding: "10px 12px",
    background: "var(--bg-elevated, #fafafa)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    marginBottom: 16,
    flexWrap: "wrap",
    alignItems: "flex-end",
  },
  label: { display: "flex", flexDirection: "column", gap: 3, fontSize: 12, color: "var(--fg-muted, #666)" },
  select: { padding: 6, fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4 },
  input: { padding: "5px 8px", fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4 },
  exportBtn: {
    padding: "6px 12px", fontSize: 13, cursor: "pointer",
    background: "#2563eb", color: "#fff", border: "none", borderRadius: 4,
    marginLeft: "auto",
  },
  summaryRow: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 12,
    marginBottom: 18,
  },
  summaryCard: {
    padding: "14px 18px",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    background: "var(--bg-elevated, #fff)",
  },
  summaryLabel: { fontSize: 12, color: "var(--fg-muted, #888)", marginBottom: 4 },
  summaryVal: { fontSize: 20, fontWeight: 600, fontVariantNumeric: "tabular-nums" },
  table: { borderCollapse: "collapse", width: "100%" },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid var(--border, #333)",
  fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid var(--border, #eee)",
  fontSize: 13,
};
