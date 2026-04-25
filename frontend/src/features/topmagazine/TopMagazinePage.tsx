import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { fmtRo, toNum } from "../evaluareagenti/shared";
import { getTopStoresByChain, type StoreRankRow, type TopStoresByChainResponse } from "./api";

function apiScopeOf(c: CompanyScope): "adp" | "sika" | "sikadp" {
  if (c === "sika") return "sika";
  if (c === "sikadp") return "sikadp";
  return "adp";
}

type Mode = "value" | "sku" | "combined";

// Cei 4 clienți KA — exact așa cum îi recunoaște backend-ul (match pe
// substring case-insensitive în RawSale.client).
const CLIENTI_KA = ["Dedeman", "Hornbach", "Leroy Merlin", "Altex"] as const;

/**
 * Top Magazine — selectezi un client KA (Dedeman, Hornbach, Leroy, Altex…)
 * și vezi magazinele acelui client ordonate după:
 *  • Valoare YTD (default)
 *  • SKU-uri distincte vândute în perioadă
 *  • Combinat 50/50 (rank normalizat pe ambele metrici)
 */
export default function TopMagazinePage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = apiScopeOf(companyScope);

  const [data, setData] = useState<TopStoresByChainResponse | null>(null);
  const [chain, setChain] = useState<string>(CLIENTI_KA[0]);
  const [mode, setMode] = useState<Mode>("value");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!chain) { setData(null); return; }
    setLoading(true);
    setError(null);
    try {
      const r = await getTopStoresByChain(chain, apiScope);
      setData(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [chain, apiScope]);

  useEffect(() => { void load(); }, [load]);

  const sortedRows = useMemo(() => {
    if (!data) return [];
    const rows = [...data.rows];
    if (mode === "value") {
      rows.sort((a, b) => toNum(b.totalAmount) - toNum(a.totalAmount));
    } else if (mode === "sku") {
      rows.sort((a, b) => b.distinctProducts - a.distinctProducts);
    } else {
      rows.sort((a, b) => b.scoreCombined - a.scoreCombined);
    }
    return rows;
  }, [data, mode]);

  const totals = useMemo(() => {
    if (!data) return { value: 0, sku: 0, rows: 0, stores: 0 };
    return data.rows.reduce(
      (acc, r) => ({
        value: acc.value + toNum(r.totalAmount),
        sku: acc.sku + r.distinctProducts,
        rows: acc.rows + r.rowCount,
        stores: acc.stores + 1,
      }),
      { value: 0, sku: 0, rows: 0, stores: 0 },
    );
  }, [data]);

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Top Magazine pe Client</h1>
          <p style={styles.lead}>
            Alege un client KA — vezi magazinele acelui client ordonate după
            valoare YTD, după SKU-uri vândute în perioadă, sau după scor
            combinat 50/50.
          </p>
        </div>
        <div style={styles.picker}>
          <label style={styles.pickerLabel}>Client</label>
          <select
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            style={styles.select}
          >
            {CLIENTI_KA.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div style={styles.modeBar}>
        <ModeBtn active={mode === "value"} onClick={() => setMode("value")}>
          După valoare
        </ModeBtn>
        <ModeBtn active={mode === "sku"} onClick={() => setMode("sku")}>
          După SKU-uri vândute
        </ModeBtn>
        <ModeBtn active={mode === "combined"} onClick={() => setMode("combined")}>
          Combinat 50/50
        </ModeBtn>
        {data?.year != null && (
          <span style={styles.yearBadge}>An: {data.year}</span>
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {loading ? (
        <div style={styles.muted}>Se încarcă…</div>
      ) : !data || sortedRows.length === 0 ? (
        <div style={styles.muted}>
          Nu există vânzări pentru {chain} în perioada selectată.
        </div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.thRank}>#</th>
                <th style={styles.thLeft}>Magazin</th>
                <th style={styles.th}>Valoare YTD</th>
                <th style={styles.th}>Facturi</th>
                <th style={styles.th}>SKU-uri vândute</th>
                <th style={styles.th}>Rank val.</th>
                <th style={styles.th}>Rank SKU</th>
                <th style={styles.thCombined}>Scor combinat</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((r, i) => (
                <Row key={`${r.storeId ?? "raw"}-${r.storeName}-${i}`} row={r} pos={i + 1} mode={mode} />
              ))}
              <tr>
                <td style={styles.tdTotal}></td>
                <td style={styles.tdTotal}>TOTAL ({totals.stores} magazine)</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.value, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.rows, 0)}</td>
                <td style={styles.tdTotalNum}>{fmtRo(totals.sku, 0)}</td>
                <td style={styles.tdTotal} colSpan={3}></td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Row({ row, pos, mode }: { row: StoreRankRow; pos: number; mode: Mode }) {
  const highlight = (col: Mode): CSSProperties =>
    col === mode
      ? { fontWeight: 700, color: "var(--cyan)" }
      : {};
  return (
    <tr>
      <td style={styles.tdRank}>{pos}</td>
      <td style={styles.tdLeft}>{row.storeName}</td>
      <td style={{ ...styles.td, ...highlight("value") }}>{fmtRo(toNum(row.totalAmount), 0)}</td>
      <td style={styles.td}>{fmtRo(row.rowCount, 0)}</td>
      <td style={{ ...styles.td, ...highlight("sku") }}>{fmtRo(row.distinctProducts, 0)}</td>
      <td style={styles.td}>{row.rankValue}</td>
      <td style={styles.td}>{row.rankSku}</td>
      <td style={{ ...styles.tdScore, ...highlight("combined") }}>{row.scoreCombined.toFixed(1)}</td>
    </tr>
  );
}

function ModeBtn({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      data-wide="true"
      data-active={active ? "true" : undefined}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { padding: "16px 8px", maxWidth: 1400 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 12, flexWrap: "wrap" },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: "0 0 4px" },
  lead: { color: "var(--muted)", fontSize: 12, margin: 0, maxWidth: 720, lineHeight: 1.5 },
  picker: {
    display: "inline-flex", alignItems: "center", gap: 8,
    padding: "6px 10px", background: "var(--bg-panel)",
    border: "1px solid var(--border)", borderRadius: 6,
  },
  pickerLabel: { fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" },
  select: {
    minWidth: 220, padding: "5px 8px", fontSize: 13,
    background: "var(--bg)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 4,
  },
  modeBar: { display: "flex", gap: 8, alignItems: "center", margin: "10px 0 14px", flexWrap: "wrap" },
  modeBtn: {
    padding: "7px 14px", fontSize: 12, fontWeight: 600,
    background: "var(--bg-panel)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer",
  },
  modeBtnActive: {
    background: "var(--cyan)", color: "#000", borderColor: "var(--cyan)",
  },
  yearBadge: {
    marginLeft: "auto", padding: "4px 10px", fontSize: 11,
    background: "var(--bg-panel)", color: "var(--muted)",
    border: "1px solid var(--border)", borderRadius: 4,
  },
  muted: { color: "var(--muted)", fontSize: 13, padding: "24px 0" },
  error: { padding: "8px 12px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)", color: "#fca5a5", borderRadius: 6, fontSize: 12, margin: "8px 0" },
  tableWrap: { background: "var(--bg-panel)", border: "1px solid var(--border)", borderRadius: 8, overflow: "auto" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: { padding: "10px 8px", textAlign: "right", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--muted)", whiteSpace: "nowrap" },
  thLeft: { padding: "10px 12px", textAlign: "left", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--muted)", whiteSpace: "nowrap" },
  thRank: { padding: "10px 8px", textAlign: "center", fontSize: 11, fontWeight: 600, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--muted)", width: 40 },
  thCombined: { padding: "10px 8px", textAlign: "right", fontSize: 11, fontWeight: 700, borderBottom: "1px solid var(--border)", background: "var(--bg-sidebar)", color: "var(--cyan)", whiteSpace: "nowrap" },
  td: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdLeft: { padding: "6px 12px", textAlign: "left", borderBottom: "1px solid var(--border)" },
  tdRank: { padding: "6px 8px", textAlign: "center", borderBottom: "1px solid var(--border)", color: "var(--muted)", fontVariantNumeric: "tabular-nums" },
  tdScore: { padding: "6px 8px", textAlign: "right", borderBottom: "1px solid var(--border)", fontVariantNumeric: "tabular-nums" },
  tdTotal: { padding: "10px 12px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", borderTop: "2px solid var(--border)" },
  tdTotalNum: { padding: "10px 8px", background: "var(--bg-sidebar)", fontWeight: 700, color: "var(--cyan)", textAlign: "right", fontVariantNumeric: "tabular-nums", borderTop: "2px solid var(--border)" },
};
