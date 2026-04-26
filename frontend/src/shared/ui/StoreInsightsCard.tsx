import { useEffect, useState, type CSSProperties } from "react";

import { apiFetch, ApiError } from "../api";

// ── Tipuri răspuns API (camelCase prin APISchema generator) ─────────────
interface AMRank {
  rank: number;
  total: number;
  pctTop: number;
}

interface AMMustListProduct {
  productId: string;
  productCode: string;
  productName: string;
  category: string | null;
  listedInStores: number;
  totalStores: number;
  monthlyAvgPerListed: string | number;
  estimatedWindowRevenue: string | number;
  estimatedWindowQuantity: string | number;
  estimated12mRevenue: string | number;
  rationale: string;
}

interface AMInsightsResponse {
  scope: string;
  store: string;
  chain: string;
  monthsWindow: number;
  rankByValue: AMRank;
  rankBySkus: AMRank;
  storeTotalValue: string | number;
  storeSkuCount: number;
  mustList: AMMustListProduct[];
}

// ── Helpers format ──────────────────────────────────────────────────────
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

// ── Stiluri (paleta și tonul restului paginii) ──────────────────────────
const card: CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
  background: "var(--surface)",
  marginBottom: 16,
};
const h: CSSProperties = {
  fontSize: 14,
  fontWeight: 700,
  color: "var(--fg)",
  marginBottom: 12,
};
const rankRow: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 12,
  marginBottom: 16,
};
const rankBox: CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 6,
  padding: 12,
  background: "var(--bg)",
};
const rankLabel: CSSProperties = {
  fontSize: 11,
  color: "var(--muted)",
  textTransform: "uppercase",
  letterSpacing: 0.5,
};
const rankValue: CSSProperties = {
  fontSize: 22,
  fontWeight: 700,
  color: "var(--cyan)",
  marginTop: 4,
};
const rankSub: CSSProperties = {
  fontSize: 11,
  color: "var(--muted)",
  marginTop: 2,
};
const tableSt: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 12,
};
const th: CSSProperties = {
  textAlign: "left",
  padding: "6px 8px",
  borderBottom: "1px solid var(--border)",
  color: "var(--muted)",
  fontWeight: 600,
};
const td: CSSProperties = {
  padding: "6px 8px",
  borderBottom: "1px solid var(--border)",
  verticalAlign: "top",
};
const tdRight: CSSProperties = {
  ...td,
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
};

interface Props {
  scope: "adp" | "sika";
  store: string;       // RawSale.client
  monthsWindow: number;
}

/**
 * Card reutilizabil care afișează:
 *  - Rank-ul magazinului (după valoare + nr SKU-uri) în scope-ul curent
 *  - Top 5 produse "obligatoriu de listat" cu estimare revenue pe 12 luni
 *
 * Folosit pe `/analiza/magazin` și `/analiza/magazin-dashboard`. Dă fetch
 * la `/api/analiza-magazin/insights` la fiecare schimbare de scope/store/months.
 */
export function StoreInsightsCard({ scope, store, monthsWindow }: Props) {
  const [data, setData] = useState<AMInsightsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!store) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<AMInsightsResponse>(
      `/api/analiza-magazin/insights?scope=${scope}&store=${encodeURIComponent(
        store,
      )}&months=${monthsWindow}`,
    )
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setError("Nu sunt suficiente date pentru insights.");
        } else {
          setError("Eroare la încărcare insights.");
        }
        setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, store, monthsWindow]);

  if (!store) return null;

  return (
    <div style={card}>
      <div style={h}>Poziție & oportunități · ultimele {monthsWindow} luni</div>

      {loading && <div style={{ color: "var(--muted)" }}>Se încarcă…</div>}
      {error && <div style={{ color: "#dc2626" }}>{error}</div>}

      {data && (
        <>
          <div style={rankRow}>
            <div style={rankBox}>
              <div style={rankLabel}>Loc după valoare</div>
              <div style={rankValue}>
                #{data.rankByValue.rank}{" "}
                <span style={{ fontSize: 13, color: "var(--muted)" }}>
                  / {data.rankByValue.total}
                </span>
              </div>
              <div style={rankSub}>
                Top {data.rankByValue.pctTop.toFixed(1)}% · vândut{" "}
                {fmtRo(toNum(data.storeTotalValue))} lei
              </div>
            </div>
            <div style={rankBox}>
              <div style={rankLabel}>Loc după SKU-uri</div>
              <div style={rankValue}>
                #{data.rankBySkus.rank}{" "}
                <span style={{ fontSize: 13, color: "var(--muted)" }}>
                  / {data.rankBySkus.total}
                </span>
              </div>
              <div style={rankSub}>
                Top {data.rankBySkus.pctTop.toFixed(1)}% ·{" "}
                {data.storeSkuCount} SKU-uri vândute
              </div>
            </div>
          </div>

          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--fg)",
              marginBottom: 6,
            }}
          >
            Top 3 mortare uscate de listat · estimare 12 luni
          </div>
          {data.mustList.length === 0 ? (
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              Magazinul are deja toate mortarele uscate relevante listate.
            </div>
          ) : (
            (() => {
              // Total estimat din toate produsele candidate.
              const totalRev = data.mustList.reduce(
                (s, p) => s + toNum(p.estimatedWindowRevenue),
                0,
              );
              const totalQty = data.mustList.reduce(
                (s, p) => s + toNum(p.estimatedWindowQuantity),
                0,
              );
              const total12m = data.mustList.reduce(
                (s, p) => s + toNum(p.estimated12mRevenue),
                0,
              );
              const storeTotal = toNum(data.storeTotalValue);
              const upliftPct =
                storeTotal > 0 ? (totalRev / storeTotal) * 100 : 0;
              return (
                <>
                  <table style={tableSt}>
                    <thead>
                      <tr>
                        <th style={th}>Produs</th>
                        <th style={th}>Categorie</th>
                        <th style={{ ...th, textAlign: "right" }}>Coverage</th>
                        <th style={{ ...th, textAlign: "right" }}>
                          Estimare {data.monthsWindow} luni
                        </th>
                        <th style={{ ...th, textAlign: "right" }}>
                          Cantitate {data.monthsWindow} luni
                        </th>
                        <th style={{ ...th, textAlign: "right" }}>
                          Anualizat 12 luni
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.mustList.map((p) => (
                        <tr key={p.productId}>
                          <td style={td}>
                            <div style={{ fontWeight: 600 }}>{p.productName}</div>
                            <div style={{ fontSize: 10, color: "var(--muted)" }}>
                              {p.productCode} · {p.rationale}
                            </div>
                          </td>
                          <td style={td}>{p.category ?? "—"}</td>
                          <td style={tdRight}>
                            {p.listedInStores}/{p.totalStores}
                          </td>
                          <td
                            style={{
                              ...tdRight,
                              fontWeight: 700,
                              color: "var(--cyan)",
                            }}
                          >
                            {fmtRo(toNum(p.estimatedWindowRevenue))} lei
                          </td>
                          <td style={tdRight}>
                            {fmtRo(toNum(p.estimatedWindowQuantity), 1)} buc
                          </td>
                          <td style={tdRight}>
                            {fmtRo(toNum(p.estimated12mRevenue))} lei
                          </td>
                        </tr>
                      ))}
                      {/* Total row */}
                      <tr style={{ background: "var(--bg)" }}>
                        <td style={{ ...td, fontWeight: 700 }} colSpan={2}>
                          Total ({data.mustList.length} produse)
                        </td>
                        <td style={tdRight}>—</td>
                        <td
                          style={{
                            ...tdRight,
                            fontWeight: 800,
                            color: "var(--cyan)",
                          }}
                        >
                          {fmtRo(totalRev)} lei
                        </td>
                        <td style={{ ...tdRight, fontWeight: 700 }}>
                          {fmtRo(totalQty, 1)} buc
                        </td>
                        <td style={{ ...tdRight, fontWeight: 700 }}>
                          {fmtRo(total12m)} lei
                        </td>
                      </tr>
                    </tbody>
                  </table>
                  <div
                    style={{
                      marginTop: 10,
                      padding: 10,
                      background: "var(--bg)",
                      borderLeft: "3px solid var(--cyan)",
                      borderRadius: 4,
                      fontSize: 12,
                    }}
                  >
                    <strong>Uplift potențial:</strong>{" "}
                    listarea celor {data.mustList.length} produse ar putea
                    aduce <strong style={{ color: "var(--cyan)" }}>
                      +{fmtRo(totalRev)} lei
                    </strong>{" "}
                    pe {data.monthsWindow} luni, adică{" "}
                    <strong style={{ color: "var(--cyan)" }}>
                      +{upliftPct.toFixed(1)}%
                    </strong>{" "}
                    peste vânzările curente ale magazinului ({fmtRo(storeTotal)} lei).
                  </div>
                </>
              );
            })()
          )}
        </>
      )}
    </div>
  );
}
