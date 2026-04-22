/**
 * Prețuri Comparative — port 1:1 din legacy `renderPretCompare` +
 * `renderPretGrid` (templates/index.html:6071+).
 *
 * 4 tab-uri (Dedeman/Leroy/Hornbach/Brico) × grid produse × brand × preț.
 * Fiecare brand are 2 sub-coloane: Produs + Preț cu culori diferite.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch, getToken } from "../../shared/api";
import { useCompanyScope } from "../../shared/ui/CompanyScopeProvider";

type PriceCell = {
  prod?: string | null;
  pret?: number | null;
  ai_status?: "found" | "not_found" | "manual" | null;
  ai_reason?: string | null;
  ai_url?: string | null;
  ai_updated_at?: string | null;
};
type BrandData = Record<string, PriceCell>;

interface GridRow {
  id: string;
  row_idx: number;
  row_num: string | null;
  group_label: string | null;
  brand_data: BrandData;
}

interface JobState {
  job_id?: string;
  status?: string;
  total?: number;
  processed?: number;
  found?: number;
  not_found?: number;
  errors?: number;
  provider?: string;
  error_msg?: string;
}

interface GridMeta {
  store: string;
  date_prices: string | null;
  brands: string[];
  imported_at: string | null;
  imported_by: string | null;
}

interface GridResponse {
  ok: boolean;
  store: string;
  meta: GridMeta;
  rows: GridRow[];
}

const STORES = ["Dedeman", "Leroy", "Hornbach", "Brico"];

// Culori legacy per brand (din templates/index.html) — overlay colorat
// deasupra tabului pentru fiecare coloană de brand.
const BRAND_COLORS: Record<string, string> = {
  ADEPLAST: "#3b82f6",
  Sika: "#ef4444",
  SIKA: "#ef4444",
  CERESIT: "#f59e0b",
  BAUMIT: "#06b6d4",
  "4 MAINI": "#facc15",
  Mapei: "#ec4899",
  MAPEI: "#ec4899",
  "Marci poprii": "#8b5cf6",
  Soudal: "#22c55e",
  SOUDAL: "#22c55e",
  Bostik: "#a855f7",
  BOSTIK: "#a855f7",
};

function brandColor(name: string): string {
  return BRAND_COLORS[name] || BRAND_COLORS[name.toUpperCase()] || "#94a3b8";
}

function fmtPrice(v: number | null | undefined): string | null {
  if (v == null || v === 0) return null;
  return new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(v);
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ro-RO", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function PreturiComparativePage() {
  const { scope } = useCompanyScope();
  const company = scope === "sika" ? "sika" : "adeplast";
  const compLabel = company === "sika" ? "Sika" : "Adeplast";
  const [grids, setGrids] = useState<Record<string, GridResponse | null>>({});
  const [activeStore, setActiveStore] = useState<string>("Dedeman");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<"grok" | "anthropic" | "openai">("grok");
  const [jobState, setJobState] = useState<JobState | null>(null);
  const [aiRunning, setAiRunning] = useState(false);

  const loadGrids = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(STORES.map((s) =>
        apiFetch<GridResponse>(
          `/api/prices/grid/${encodeURIComponent(s)}?company=${company}`
        ).catch(() => null)
      ));
      const map: Record<string, GridResponse | null> = {};
      STORES.forEach((s, i) => { map[s] = results[i]; });
      setGrids(map);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, [company]);

  useEffect(() => { loadGrids(); }, [loadGrids]);

  // Poll active job on mount + when store changes
  useEffect(() => {
    let cancelled = false;
    apiFetch<{ ok: boolean; job: JobState | null; is_active: boolean }>(
      `/api/prices/grid/${encodeURIComponent(activeStore)}/ai_update/status?company=${company}`
    ).then((r) => {
      if (!cancelled && r.job) {
        setJobState(r.job);
        setAiRunning(r.is_active);
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeStore, company]);

  // Poll while job is running
  useEffect(() => {
    if (!aiRunning || !jobState?.job_id) return;
    const id = setInterval(async () => {
      try {
        const r = await apiFetch<{ ok: boolean; job: JobState }>(
          `/api/prices/grid/ai_update/${jobState.job_id}`
        );
        setJobState(r.job);
        if (r.job.status !== "running" && r.job.status !== "pending") {
          setAiRunning(false);
          await loadGrids();  // Reload cu prețurile noi
        }
      } catch { /* ignore */ }
    }, 2500);
    return () => clearInterval(id);
  }, [aiRunning, jobState?.job_id, loadGrids]);

  const startAi = async () => {
    try {
      const r = await apiFetch<{ ok: boolean; job_id: string; total: number; provider: string }>(
        `/api/prices/grid/${encodeURIComponent(activeStore)}/ai_update/start?company=${company}`,
        { method: "POST", body: JSON.stringify({ provider }) },
      );
      setJobState({ job_id: r.job_id, total: r.total, processed: 0, status: "running", provider: r.provider });
      setAiRunning(true);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Eroare pornire AI");
    }
  };

  const cancelAi = async () => {
    if (!jobState?.job_id) return;
    try {
      await apiFetch(`/api/prices/grid/ai_update/${jobState.job_id}/cancel`, { method: "POST" });
      setAiRunning(false);
    } catch { /* ignore */ }
  };

  const updateCell = async (rowIdx: number, brand: string, newPret: string) => {
    try {
      await apiFetch(
        `/api/prices/grid/${encodeURIComponent(activeStore)}/cell?company=${company}`,
        {
          method: "PUT",
          body: JSON.stringify({ row_idx: rowIdx, brand, pret: newPret }),
        },
      );
      await loadGrids();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Eroare update");
    }
  };

  const current = grids[activeStore];
  const brands = useMemo(() => current?.meta.brands ?? [], [current]);

  const [exporting, setExporting] = useState(false);
  async function exportExcel() {
    setExporting(true);
    try {
      const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
      const resp = await fetch(
        `${apiBase}/api/prices/grid-export.xlsx?company=${company}`,
        { headers: { Authorization: `Bearer ${getToken() ?? ""}` } },
      );
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || `HTTP ${resp.status}`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `preturi-comparative-${company}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Eroare export");
    } finally {
      setExporting(false);
    }
  }

  if (loading) return <div style={{ padding: 20, color: "var(--muted)" }}>Se încarcă…</div>;
  if (error) return <div style={{ padding: 20, color: "var(--red)" }}>{error}</div>;

  return (
    <div style={{
      padding: "4px 4px 20px", color: "var(--text)",
      // Zoom out să încapă grid 15 coloane (# + 7 branduri × 2) într-un view
      zoom: 0.80 as unknown as number,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          🔍 Prețuri Comparative {compLabel} vs Concurență
        </h2>
        <div style={toolbarStyle}>
          <button
            type="button"
            data-compact="true"
            onClick={exportExcel}
            disabled={exporting}
            style={{
              ...toolbarItemStyle,
              background: "#fff", color: "#16a34a",
              border: "1px solid #16a34a55",
              opacity: exporting ? 0.6 : 1,
            }}
            title="Descarcă toate cele 4 magazine ca Excel"
          >
            {exporting ? "..." : "⬇ Excel"}
          </button>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as typeof provider)}
            disabled={aiRunning}
            data-compact="true"
            style={{
              ...toolbarItemStyle,
              background: "#fff",
              border: "1px solid var(--border)",
              color: "var(--text)",
              textAlign: "center",
              textAlignLast: "center" as const,
              appearance: "none" as const,
              WebkitAppearance: "none" as const,
            }}
            title="Provider AI"
          >
            <option value="grok">🚀 Grok</option>
            <option value="anthropic">🤖 Claude</option>
            <option value="openai">💬 GPT-4o</option>
          </select>
          {aiRunning ? (
            <button
              type="button"
              onClick={cancelAi}
              data-compact="true"
              style={{
                ...toolbarItemStyle,
                background: "#fff",
                color: "var(--red)",
                border: "1px solid var(--red)55",
              }}
            >
              ⏹ {jobState?.processed}/{jobState?.total}
            </button>
          ) : (
            <button
              type="button"
              onClick={startAi}
              data-compact="true"
              style={{
                ...toolbarItemStyle,
                background: "#fff",
                color: "#a855f7",
                border: "1px solid #a855f755",
              }}
              title="Actualizează prețurile cu AI"
            >
              🤖 AI
            </button>
          )}
        </div>
      </div>

      {/* AI job progress bar */}
      {jobState && jobState.total !== undefined && jobState.total > 0 && (
        <div style={{
          marginBottom: 12, padding: "8px 12px", borderRadius: 6,
          background: aiRunning ? "rgba(168,85,247,0.08)" : "rgba(34,197,94,0.08)",
          border: `1px solid ${aiRunning ? "rgba(168,85,247,0.3)" : "rgba(34,197,94,0.3)"}`,
          fontSize: 12, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
        }}>
          <span style={{ fontWeight: 600, color: aiRunning ? "#a855f7" : "var(--green)" }}>
            {aiRunning ? "⏳ AI rulează" : jobState.status === "done" ? "✅ Job gata" : jobState.status === "cancelled" ? "🚫 Anulat" : `📊 Ultim job: ${jobState.status}`}
          </span>
          <span style={{ color: "var(--muted)" }}>
            provider: <b>{jobState.provider || provider}</b>
          </span>
          <span>
            <b style={{ color: "var(--green)" }}>{jobState.found || 0}</b> găsite ·{" "}
            <b style={{ color: "var(--red)" }}>{jobState.not_found || 0}</b> nu găsite ·{" "}
            <b style={{ color: "var(--muted)" }}>{jobState.errors || 0}</b> erori
          </span>
          <span style={{ marginLeft: "auto", color: "var(--muted)" }}>
            {jobState.processed || 0} / {jobState.total} procesate
          </span>
          {jobState.error_msg && <span style={{ color: "var(--red)", width: "100%" }}>❌ {jobState.error_msg}</span>}
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 0 }}>
        {STORES.map((s) => {
          const active = s === activeStore;
          const rows = grids[s]?.rows?.length ?? 0;
          return (
            <button
              key={s}
              onClick={() => setActiveStore(s)}
              style={{
                padding: "9px 20px",
                border: "1px solid var(--border)",
                borderBottom: active ? "none" : "1px solid var(--border)",
                borderRadius: "8px 8px 0 0",
                background: active ? "var(--card)" : "var(--bg-elevated)",
                color: active ? "var(--accent)" : "var(--muted)",
                cursor: "pointer", fontSize: 13,
                fontWeight: active ? 700 : 500,
              }}
            >
              {s} <small style={{ opacity: 0.6 }}>({rows})</small>
            </button>
          );
        })}
      </div>

      {/* Active panel */}
      <div style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "0 8px 8px 8px",
        padding: 14,
        overflowX: "auto",
      }}>
        {current ? (
          <>
            <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10, display: "flex", gap: 16, flexWrap: "wrap" }}>
              <span>📅 Data prețuri: <b style={{ color: "var(--text)" }}>{current.meta.date_prices || "—"}</b></span>
              <span>Importat: {fmtDateTime(current.meta.imported_at)}</span>
              <span style={{ marginLeft: "auto" }}>{current.rows.length} produse · {brands.length} branduri</span>
            </div>

            <BrandGrid rows={current.rows} brands={brands} onEditCell={updateCell} />
          </>
        ) : (
          <div style={{ padding: 40, color: "var(--muted)", textAlign: "center" }}>
            Nu există date pentru {activeStore}. Importă fișierul Excel.
          </div>
        )}
      </div>
    </div>
  );
}

// Culori bulină per ai_status (port 1:1 din legacy templates/index.html:6247)
const AI_STATUS_STYLE: Record<string, { dot: string; bg: string; title: string }> = {
  found:     { dot: "#22c55e", bg: "rgba(34,197,94,0.12)", title: "Confirmat de AI" },
  not_found: { dot: "#ef4444", bg: "rgba(239,68,68,0.10)", title: "AI nu a găsit. Click pentru a introduce manual." },
  manual:    { dot: "#3b82f6", bg: "rgba(59,130,246,0.12)", title: "Preț introdus manual" },
  default:   { dot: "#eab308", bg: "rgba(234,179,8,0.10)", title: "Neactualizat — preț din import, nu confirmat" },
};

function BrandGrid({
  rows, brands, onEditCell,
}: {
  rows: GridRow[]; brands: string[];
  onEditCell: (rowIdx: number, brand: string, newPret: string) => void;
}) {
  const handleEdit = (rowIdx: number, brand: string, currentPret: number | null | undefined) => {
    const current = currentPret == null || Number.isNaN(currentPret) ? "" : String(currentPret);
    const val = window.prompt(
      `Preț pentru ${brand} (row ${rowIdx + 1}):\nLasă gol pentru a șterge.`,
      current,
    );
    if (val === null) return;
    onEditCell(rowIdx, brand, val.trim());
  };

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        {/* Top row: brand name (span 2) */}
        <tr>
          <th style={{ ...thStyle, width: 36 }}>#</th>
          {brands.map((b) => {
            const c = brandColor(b);
            return (
              <th key={b} colSpan={2} style={{
                ...thStyle,
                textAlign: "center",
                color: c,
                borderBottom: `2px solid ${c}55`,
                fontSize: 13, fontWeight: 700,
                padding: "10px 6px",
              }}>
                {b}
              </th>
            );
          })}
        </tr>
        {/* Second row: Produs / Preț sub-headers */}
        <tr>
          <th style={{ ...thStyle }}></th>
          {brands.flatMap((b) => {
            const c = brandColor(b);
            return [
              <th key={`${b}-prod`} style={{ ...subThStyle, color: c, minWidth: 160 }}>Produs</th>,
              <th key={`${b}-pret`} style={{ ...subThStyle, color: c, textAlign: "right", minWidth: 70 }}>Preț</th>,
            ];
          })}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, idx) => (
          <tr key={r.id} style={{
            borderBottom: "1px solid var(--border)",
            background: idx % 2 === 1 ? "rgba(148,163,184,0.03)" : "transparent",
          }}>
            <td style={{ ...tdStyle, color: "var(--muted)", textAlign: "center" }}>
              {r.row_num || idx + 1}
            </td>
            {brands.flatMap((b) => {
              const cell: PriceCell = r.brand_data[b] || r.brand_data[b.toUpperCase()] || {};
              const prod = cell.prod || "";
              const pretFmt = fmtPrice(cell.pret);
              const editable = !!prod;
              // Status bulină: legacy color codes
              const statusKey = cell.ai_status && AI_STATUS_STYLE[cell.ai_status]
                ? cell.ai_status
                : (prod ? "default" : null);
              const style = statusKey ? AI_STATUS_STYLE[statusKey] : null;
              const title = [
                prod,
                cell.ai_updated_at && `${statusKey === "manual" ? "manual" : "AI"}: ${cell.ai_updated_at}`,
                cell.ai_url,
                cell.ai_reason,
                editable ? "Click pentru editare manuală" : "",
              ].filter(Boolean).join(" · ");
              return [
                <td key={`${b}-prod`} style={{
                  ...tdStyle, color: prod ? "var(--text)" : "var(--muted)",
                  opacity: prod ? 1 : 0.4,
                }} title={title}>
                  {prod || "—"}
                </td>,
                <td key={`${b}-pret`} style={{
                  ...tdStyle, textAlign: "right",
                  background: style?.bg || "transparent",
                  cursor: editable ? "pointer" : "default",
                  fontVariantNumeric: "tabular-nums",
                }} title={title}
                  onClick={editable ? () => handleEdit(r.row_idx, b, cell.pret ?? null) : undefined}
                >
                  {style && (
                    <span style={{ color: style.dot, marginRight: 4, fontSize: 11 }}
                          title={style.title}>●</span>
                  )}
                  {pretFmt ? (
                    <span style={{ fontWeight: 600, color: "var(--text)" }}>{pretFmt}</span>
                  ) : (
                    <span style={{ color: "var(--muted)", opacity: 0.4 }}>—</span>
                  )}
                </td>,
              ];
            })}
          </tr>
        ))}
        {rows.length === 0 && (
          <tr>
            <td colSpan={brands.length * 2 + 1} style={{ padding: 30, color: "var(--muted)", textAlign: "center" }}>
              Niciun produs. Importă fișierul Excel.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

// Toolbar — 3 butoane mici și egale (dimensiune naturală cu min-width global).
const toolbarStyle: React.CSSProperties = {
  marginLeft: "auto",
  display: "flex",
  gap: 6,
  alignItems: "center",
  flexWrap: "wrap",
};
const toolbarItemStyle: React.CSSProperties = {
  flex: "0 0 auto",
};

const thStyle: React.CSSProperties = {
  padding: "10px 8px", textAlign: "left",
  color: "var(--muted)", fontSize: 11,
  borderBottom: "1px solid var(--border)",
  background: "var(--bg-elevated)",
  fontWeight: 600, letterSpacing: 0.3,
};
const subThStyle: React.CSSProperties = {
  padding: "6px 8px", textAlign: "left",
  fontSize: 10, fontWeight: 600,
  borderBottom: "1px solid var(--border)",
  background: "var(--bg-elevated)",
  textTransform: "uppercase",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 8px", fontSize: 13,
};
