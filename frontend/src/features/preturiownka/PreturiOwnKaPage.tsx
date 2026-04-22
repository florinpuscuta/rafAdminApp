/**
 * Adeplast / Sika cross-KA — port 1:1 din legacy `renderPretCross` +
 * endpoint `GET /api/price_grid/own_cross_ka`.
 *
 * Pivot matrix: produse proprii × 4 rețele KA (Dedeman/Leroy/Hornbach/Brico)
 * cu min/max/spread% per produs.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, apiFetch } from "../../shared/api";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { downloadTableAsCsv } from "../../shared/utils/exportCsv";

interface PriceCell {
  prod: string;
  pret: number | null;
  ai_status?: string;
  ai_updated_at?: string;
}

interface ProductRow {
  canonical_name: string;
  prices: Record<string, PriceCell>;
  min_price: number;
  max_price: number;
  spread_pct: number;
}

interface CrossKaResponse {
  ok: boolean;
  brand: string;
  stores: string[];
  products: ProductRow[];
}

function fmtPrice(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  return new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);
}

export default function PreturiOwnKaPage() {
  const { scope } = useCompanyScope();
  const company = scope === "sika" ? "sika" : "adeplast";
  const [data, setData] = useState<CrossKaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const tableRef = useRef<HTMLTableElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<CrossKaResponse>(`/api/prices/own_cross_ka?company=${company}`)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Eroare"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [company]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.toUpperCase();
    if (!q) return data.products;
    return data.products.filter((p) => p.canonical_name.toUpperCase().includes(q));
  }, [data, search]);

  if (loading) return <div style={{ padding: 20, color: "var(--muted)" }}>Se încarcă…</div>;
  if (error) return <div style={{ padding: 20, color: "var(--red)" }}>{error}</div>;
  if (!data) return null;

  return (
    <div style={{
      padding: "4px 4px 20px", color: "var(--text)",
      zoom: 0.80 as unknown as number,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          🔀 {data.brand} cross-KA
        </h2>
        <button
          type="button"
          data-compact="true"
          onClick={() => downloadTableAsCsv(tableRef.current, `${data.brand}-cross-ka.csv`)}
          style={{
            padding: "6px 10px", fontSize: 12, fontWeight: 600,
            background: "#16a34a", color: "#fff", border: "none",
            borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap", minHeight: 34,
          }}
          title="Descarcă tabelul ca Excel"
        >
          ⬇ Excel
        </button>
        <input
          type="text"
          placeholder="Caută produs…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "7px 12px", borderRadius: 6,
            border: "1px solid var(--border)", background: "var(--bg)",
            color: "var(--text)", fontSize: 13, minWidth: 220,
          }}
        />
      </div>

      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>
        {data.products.length} produse · {filtered.length} afișate · spread = (max-min)/min × 100
      </div>

      <div style={{ overflowX: "auto", background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 }}>
        <table ref={tableRef} style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "var(--bg-elevated)" }}>
              <th style={{ ...thStyle, textAlign: "left", minWidth: 200 }}>Produs</th>
              {data.stores.map((s) => (
                <th key={s} style={thStyle}>{s}</th>
              ))}
              <th style={thStyle}>Min</th>
              <th style={thStyle}>Max</th>
              <th style={{ ...thStyle, minWidth: 80 }}>Spread</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p, i) => {
              const spreadColor = p.spread_pct >= 10 ? "var(--red)" : p.spread_pct >= 3 ? "var(--orange)" : "var(--green)";
              return (
                <tr key={`${p.canonical_name}-${i}`} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ ...tdStyle, fontWeight: 600 }}>{p.canonical_name}</td>
                  {data.stores.map((s) => {
                    const cell = p.prices[s];
                    if (!cell || cell.pret == null) {
                      return <td key={s} style={{ ...tdStyle, textAlign: "center", color: "var(--muted)", opacity: 0.4 }}>—</td>;
                    }
                    const isMin = cell.pret === p.min_price && p.spread_pct > 0;
                    const isMax = cell.pret === p.max_price && p.spread_pct > 0;
                    return (
                      <td key={s} style={{
                        ...tdStyle, textAlign: "right", fontVariantNumeric: "tabular-nums",
                        fontWeight: isMin || isMax ? 700 : 500,
                        color: isMin ? "var(--green)" : isMax ? "var(--red)" : "var(--text)",
                      }} title={cell.prod}>
                        {fmtPrice(cell.pret)}
                      </td>
                    );
                  })}
                  <td style={{ ...tdStyle, textAlign: "right", color: "var(--green)", fontWeight: 600 }}>
                    {fmtPrice(p.min_price)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", color: "var(--red)", fontWeight: 600 }}>
                    {fmtPrice(p.max_price)}
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right", fontWeight: 700, color: spreadColor }}>
                    {p.spread_pct.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={data.stores.length + 4} style={{ padding: 30, textAlign: "center", color: "var(--muted)" }}>
                  Niciun produs găsit
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "10px 10px", textAlign: "right",
  fontSize: 11, fontWeight: 600, color: "var(--muted)",
  textTransform: "uppercase", letterSpacing: 0.4,
  borderBottom: "1px solid var(--border)",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 10px", color: "var(--text)",
};
