/**
 * Panouri & Standuri — port 1:1 al `renderPanouri` + `renderPanouriStore`
 * (templates/index.html:13347-13731).
 *
 * 2 vederi:
 *   1. Main: KPI cards + Chain pills + Agent table + Search + Store grid
 *   2. Store detail: Add panel form + Panel list + (TODO) Photo grid
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch, getToken } from "../../shared/api";
import { PhotoUploader } from "../../shared/ui/PhotoUploader";
import { useToast } from "../../shared/ui/ToastProvider";
import { useConfirm } from "../../shared/ui/ConfirmDialog";
import {
  addPanel,
  deletePanel,
  getStoreDetail,
  listStores,
  updatePanel,
} from "./api";
import type {
  PanouStandRow,
  StoreDetailResponse,
  StoreListItem,
} from "./types";

const CHAIN_COLORS: Record<string, string> = {
  DEDEMAN: "#22c55e", ALTEX: "#f59e0b", LEROY: "#ef4444",
  HORNBACH: "#3b82f6", BRICO: "#8b5cf6", BRICOSTORE: "#8b5cf6",
  PRAKTIKER: "#ec4899", PUSKIN: "#06b6d4",
};

const TYPE_LABELS: Record<string, string> = {
  panou: "Panou publicitar", stand: "Stand expunere", totem: "Totem",
  banner: "Banner", gondola: "Capsa gondola", altele: "Altele",
};
const TYPE_COLORS: Record<string, string> = {
  panou: "#f59e0b", stand: "#22c55e", totem: "#8b5cf6",
  banner: "#ef4444", gondola: "#3b82f6", altele: "#6b7280",
};
const TYPE_ICONS: Record<string, string> = {
  panou: "🖼️", stand: "🛍️", totem: "🏆",
  banner: "🏳️", gondola: "🛍️", altele: "📦",
};

function chainOf(storeName: string): string {
  return (storeName || "").split(" ")[0] || "";
}

export default function MktPanouriPage() {
  const [currentStore, setCurrentStore] = useState<string | null>(null);

  if (currentStore) {
    return (
      <StoreDetail
        storeName={currentStore}
        onBack={() => setCurrentStore(null)}
      />
    );
  }
  return <MainView onOpenStore={setCurrentStore} />;
}

// ── Main view ───────────────────────────────────────────────────────────────

function MainView({ onOpenStore }: { onOpenStore: (s: string) => void }) {
  const [stores, setStores] = useState<StoreListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [chainFilter, setChainFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    listStores()
      .then((r) => !cancelled && setStores(r.stores || []))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Eroare"))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const agents = useMemo(() => {
    const s = new Set(stores.map((x) => x.agent).filter(Boolean));
    return Array.from(s).sort();
  }, [stores]);
  const chains = useMemo(() => {
    const s = new Set(stores.map((x) => chainOf(x.name)));
    return Array.from(s).sort();
  }, [stores]);

  const kpis = useMemo(() => {
    const totalStores = stores.length;
    const storesWithPanels = stores.filter((s) => s.panelCount > 0).length;
    const storesWithPhotos = stores.filter((s) => s.photoCount > 0).length;
    const totalPanels = stores.reduce((acc, s) => acc + (s.panelCount || 0), 0);
    const totalPhotos = stores.reduce((acc, s) => acc + (s.photoCount || 0), 0);
    const coverage = totalStores > 0 ? Math.round(storesWithPanels / totalStores * 100) : 0;
    return { totalStores, storesWithPanels, storesWithPhotos, totalPanels, totalPhotos, coverage };
  }, [stores]);

  const agentStats = useMemo(() => {
    const map: Record<string, { stores: number; panels: number; photos: number; withPanels: number }> = {};
    for (const s of stores) {
      const ag = s.agent || "Neatribuit";
      if (!map[ag]) map[ag] = { stores: 0, panels: 0, photos: 0, withPanels: 0 };
      map[ag].stores++;
      map[ag].panels += s.panelCount || 0;
      map[ag].photos += s.photoCount || 0;
      if (s.panelCount > 0) map[ag].withPanels++;
    }
    return map;
  }, [stores]);

  const chainStats = useMemo(() => {
    const map: Record<string, { stores: number; panels: number; photos: number; withPanels: number }> = {};
    for (const s of stores) {
      const ch = chainOf(s.name);
      if (!map[ch]) map[ch] = { stores: 0, panels: 0, photos: 0, withPanels: 0 };
      map[ch].stores++;
      map[ch].panels += s.panelCount || 0;
      map[ch].photos += s.photoCount || 0;
      if (s.panelCount > 0) map[ch].withPanels++;
    }
    return map;
  }, [stores]);

  const filtered = useMemo(() => {
    const q = search.toUpperCase();
    return stores.filter((s) => {
      if (q && !s.name.toUpperCase().includes(q)) return false;
      if (agentFilter && s.agent !== agentFilter) return false;
      if (chainFilter && !s.name.toUpperCase().startsWith(chainFilter.toUpperCase())) return false;
      return true;
    });
  }, [stores, search, agentFilter, chainFilter]);

  const grouped = useMemo(() => {
    const g: Record<string, StoreListItem[]> = {};
    for (const s of filtered) {
      const ch = chainOf(s.name);
      (g[ch] ||= []).push(s);
    }
    return g;
  }, [filtered]);

  if (loading) return <div style={{ padding: 20, color: "var(--muted)" }}>Se încarcă…</div>;
  if (error) return <div style={{ padding: 20, color: "var(--red)" }}>{error}</div>;

  return (
    <div style={{ padding: "4px 4px 20px", maxWidth: 1200, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 4px", color: "#f59e0b", fontSize: 20 }}>
        🖼️ Panouri & Standuri
      </h2>
      <p style={{ color: "var(--muted)", marginBottom: 16, fontSize: 13 }}>
        Gestionează panourile și standurile din fiecare magazin. Click pe un magazin pentru detalii.
      </p>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8, marginBottom: 14 }}>
        <KpiCard value={kpis.totalPanels} label="Total Panouri" color="#f59e0b" />
        <KpiCard value={kpis.totalPhotos} label="Total Fotografii" color="#3b82f6" />
        <KpiCard
          value={<>{kpis.storesWithPanels}<span style={{ fontSize: 12, fontWeight: 400, color: "var(--muted)" }}>/{kpis.totalStores}</span></>}
          label="Magazine cu Panouri" color="#22c55e"
        />
        <KpiCard
          value={`${kpis.coverage}%`} label="Acoperire"
          color={kpis.coverage >= 75 ? "#22c55e" : kpis.coverage >= 40 ? "#f59e0b" : "#ef4444"}
        />
      </div>

      {/* Chain selector — single-line trigger, tap to expand list */}
      <ChainSelector
        chainStats={chainStats}
        selected={chainFilter}
        onSelect={setChainFilter}
      />

      {/* Agent table (collapsible) */}
      <details style={{ marginBottom: 20, background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10 }}>
        <summary style={{ padding: "12px 16px", cursor: "pointer", fontWeight: 600, color: "var(--accent)", fontSize: 13 }}>
          👥 Situație per Agent ({agents.length} agenți)
        </summary>
        <div style={{ padding: "0 8px 8px", display: "flex", flexDirection: "column", gap: 6 }}>
          {Object.entries(agentStats).sort().map(([ag, a]) => {
            const pct = a.stores > 0 ? Math.round(a.withPanels / a.stores * 100) : 0;
            const barColor = pct >= 75 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
            return (
              <div
                key={ag}
                style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "8px 10px",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <div style={{ flex: 1, minWidth: 0, fontWeight: 600, fontSize: 12, wordBreak: "break-word" }}>
                  {ag}
                </div>
                <span title="Magazine" style={{
                  flex: "0 0 46px", fontSize: 12, color: "var(--muted)",
                  whiteSpace: "nowrap", display: "inline-flex",
                  justifyContent: "space-between", gap: 4,
                }}>
                  <span>🏬</span><span>{a.stores}</span>
                </span>
                <span title="Panouri" style={{
                  flex: "0 0 48px", fontSize: 12, fontWeight: 700, color: "#f59e0b",
                  whiteSpace: "nowrap", display: "inline-flex",
                  justifyContent: "space-between", gap: 4,
                }}>
                  <span>🖼️</span><span>{a.panels}</span>
                </span>
                <span title="Poze" style={{
                  flex: "0 0 48px", fontSize: 12, color: "var(--accent)",
                  whiteSpace: "nowrap", display: "inline-flex",
                  justifyContent: "space-between", gap: 4,
                }}>
                  <span>📷</span><span>{a.photos}</span>
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 4, flex: "0 0 80px" }}>
                  <div style={{ flex: 1, height: 5, background: "rgba(148,163,184,0.15)", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", background: barColor, borderRadius: 3 }} />
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: barColor, minWidth: 28, textAlign: "right" }}>{pct}%</span>
                </div>
              </div>
            );
          })}
        </div>
      </details>

      {/* Filters */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <input type="text" placeholder="🔎 Caută magazin…"
          value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, minWidth: 220, padding: "9px 12px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 13 }}
        />
        <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}
          style={{ padding: 9, borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 13 }}>
          <option value="">Toți agenții</option>
          {agents.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={chainFilter} onChange={(e) => setChainFilter(e.target.value)}
          style={{ padding: 9, borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 13 }}>
          <option value="">Toate rețelele</option>
          {chains.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{filtered.length} magazine</span>
      </div>

      {/* Store groups */}
      {Object.keys(grouped).length === 0 && (
        <div style={{ textAlign: "center", padding: 40, color: "var(--muted)" }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🔎</div>
          Niciun magazin găsit
        </div>
      )}
      {Object.entries(grouped).sort().map(([ch, storesArr]) => {
        const color = CHAIN_COLORS[ch.toUpperCase()] || "var(--accent)";
        return (
          <div key={ch} style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, padding: "6px 12px" }}>
              <span style={{ width: 4, height: 18, background: color, borderRadius: 2, display: "inline-block" }} />
              <span style={{ fontWeight: 700, fontSize: 13, color }}>{ch}</span>
              <span style={{ color: "var(--muted)", fontSize: 11 }}>({storesArr.length})</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10, paddingLeft: 12 }}>
              {storesArr.map((s) => (
                <StoreCard key={s.name} store={s} color={color} onClick={() => onOpenStore(s.name)} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function KpiCard({ value, label, color }: { value: React.ReactNode; label: string; color: string }) {
  return (
    <div style={{
      background: `linear-gradient(135deg, ${color}22, ${color}11)`,
      border: `1px solid ${color}44`,
      borderRadius: 10, padding: "8px 10px", textAlign: "center",
      display: "flex", flexDirection: "column", justifyContent: "center",
      minHeight: 58,
    }}>
      <div style={{ fontSize: 20, fontWeight: 800, color, lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 10.5, color: "var(--muted)", marginTop: 2, lineHeight: 1.25 }}>{label}</div>
    </div>
  );
}

function ChainSelector({
  chainStats, selected, onSelect,
}: {
  chainStats: Record<string, { stores: number; panels: number; photos: number; withPanels: number }>;
  selected: string;
  onSelect: (ch: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(chainStats).sort();
  const selectedStats = selected ? chainStats[selected] : null;
  const totalPanels = entries.reduce((acc, [, s]) => acc + s.panels, 0);
  const totalStores = entries.reduce((acc, [, s]) => acc + s.stores, 0);
  const totalPhotos = entries.reduce((acc, [, s]) => acc + s.photos, 0);
  const selColor = selected ? (CHAIN_COLORS[selected.toUpperCase()] || "var(--accent)") : "var(--text)";

  return (
    <div style={{ marginBottom: 14 }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: 10, padding: "10px 12px", cursor: "pointer",
          color: "var(--text)", fontSize: 13, textAlign: "left",
        }}
      >
        <span style={{ fontWeight: 600, color: "var(--muted)" }}>Rețea:</span>
        <span style={{ fontWeight: 700, color: selColor }}>
          {selected || "Toate"}
        </span>
        <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: "auto" }}>
          {selected
            ? `${selectedStats?.panels ?? 0} pan · ${selectedStats?.stores ?? 0} mag · ${selectedStats?.photos ?? 0} poze`
            : `${totalPanels} pan · ${totalStores} mag · ${totalPhotos} poze`}
        </span>
        <span style={{ color: "var(--muted)", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>▾</span>
      </button>
      {open && (
        <div style={{
          marginTop: 6, maxHeight: 260, overflowY: "auto",
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: 10, padding: 4,
        }}>
          <ChainOption
            label="Toate rețelele" color="var(--text)"
            panels={totalPanels} stores={totalStores} photos={totalPhotos}
            active={!selected}
            onClick={() => { onSelect(""); setOpen(false); }}
          />
          {entries.map(([ch, s]) => (
            <ChainOption
              key={ch} label={ch}
              color={CHAIN_COLORS[ch.toUpperCase()] || "var(--accent)"}
              panels={s.panels} stores={s.stores} photos={s.photos}
              active={selected === ch}
              onClick={() => { onSelect(ch); setOpen(false); }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ChainOption({
  label, color, panels, stores, photos, active, onClick,
}: {
  label: string; color: string; panels: number; stores: number; photos: number;
  active: boolean; onClick: () => void;
}) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "8px 10px", borderRadius: 8, cursor: "pointer",
        background: active ? "rgba(37,99,235,0.08)" : "transparent",
      }}
    >
      <span style={{ width: 4, height: 16, borderRadius: 2, background: color, flex: "0 0 auto" }} />
      <span style={{ fontWeight: 700, fontSize: 13, color, flex: "0 0 auto" }}>{label}</span>
      <span style={{ color: "var(--muted)", fontSize: 11, marginLeft: "auto", whiteSpace: "nowrap" }}>
        {panels} pan · {stores} mag · {photos} poze
      </span>
    </div>
  );
}

function StoreCard({ store, color, onClick }: {
  store: StoreListItem; color: string; onClick: () => void;
}) {
  const hasPanels = store.panelCount > 0;
  return (
    <div onClick={onClick} style={{
      background: "var(--card)", border: "1px solid var(--border)",
      borderRadius: 10, padding: 12, cursor: "pointer",
      display: "flex", alignItems: "center", gap: 10, transition: "all .2s",
    }} onMouseOver={(e) => {
      e.currentTarget.style.borderColor = color;
    }} onMouseOut={(e) => {
      e.currentTarget.style.borderColor = "var(--border)";
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: 8,
        background: `linear-gradient(135deg, ${color}22, ${color}44)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 18, flexShrink: 0,
      }}>{hasPanels ? "🖼️" : "📂"}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontWeight: 600, fontSize: 12, whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis",
        }} title={store.name}>{store.name}</div>
        <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>{store.agent || "Neatribuit"}</div>
      </div>
      {hasPanels && (
        <span style={{ background: "#22c55e", color: "#000", padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 600 }}>
          {store.panelCount}
        </span>
      )}
    </div>
  );
}

// ── Store detail view ───────────────────────────────────────────────────────

function StoreDetail({ storeName, onBack }: { storeName: string; onBack: () => void }) {
  const [data, setData] = useState<StoreDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const confirm = useConfirm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await getStoreDetail(storeName);
      setData(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, [storeName]);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async (payload: {
    panelType: string; title: string; widthCm: string; heightCm: string;
    locationInStore: string; notes: string;
  }) => {
    try {
      await addPanel(storeName, {
        panelType: payload.panelType,
        title: payload.title,
        widthCm: payload.widthCm ? parseFloat(payload.widthCm) : null,
        heightCm: payload.heightCm ? parseFloat(payload.heightCm) : null,
        locationInStore: payload.locationInStore,
        notes: payload.notes,
      });
      toast.success("Panou adăugat");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  };

  const handleUploadPhotos = async (files: FileList) => {
    const token = getToken();
    const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("images", f));
    try {
      const resp = await fetch(
        `${apiBase}/api/marketing/panouri/store/${encodeURIComponent(storeName)}/photos`,
        {
          method: "POST",
          body: form,
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        },
      );
      if (!resp.ok) throw new ApiError(resp.status, resp.statusText);
      const d = await resp.json();
      toast.success(`${d.uploaded} poze încărcate`);
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare upload");
    }
  };

  const handleRotate = async (photoId: string, direction: "left" | "right") => {
    try {
      await apiFetch(`/api/gallery/photos/${photoId}/rotate?direction=${direction}`, {
        method: "POST",
      });
      toast.success("Rotită");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare rotire");
    }
  };

  const handleDelete = async (p: PanouStandRow) => {
    const ok = await confirm({
      title: "Ștergi panoul?",
      message: `${p.title || TYPE_LABELS[p.panelType] || p.panelType}`,
      danger: true,
    });
    if (!ok) return;
    try {
      await deletePanel(p.id);
      toast.success("Șters");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  };

  return (
    <div style={{ padding: "4px 4px 20px", maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <button onClick={onBack} style={{ padding: "7px 14px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--card)", color: "var(--text)", cursor: "pointer", fontSize: 13 }}>
          ← Înapoi
        </button>
        <h2 style={{ margin: 0, color: "#f59e0b", fontSize: 18 }}>🖼️ {storeName}</h2>
      </div>

      {error && <div style={{ color: "var(--red)", padding: 12 }}>{error}</div>}
      {loading && !data && <div style={{ color: "var(--muted)", padding: 12 }}>Se încarcă…</div>}

      {data && <AddPanelForm onSubmit={handleAdd} />}

      {data && (
        <>
          <h3 style={{ marginBottom: 12, color: "var(--text)", fontSize: 14 }}>
            📋 Panouri & Standuri ({data.panels.length})
          </h3>
          {data.panels.length === 0 ? (
            <div style={{
              textAlign: "center", padding: 24, color: "var(--muted)",
              background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10,
            }}>
              <div style={{ fontSize: 32, marginBottom: 6 }}>🖼️</div>
              Niciun panou sau stand înregistrat.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
              {data.panels.map((p) => (
                <PanelCard key={p.id} panel={p} onDelete={() => handleDelete(p)} onUpdated={load} />
              ))}
            </div>
          )}

          <div style={{
            marginTop: 20, marginBottom: 12,
            display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
          }}>
            <h3 style={{ margin: 0, color: "var(--text)", fontSize: 14 }}>
              📷 Fotografii ({data.photos.length})
            </h3>
            <div style={{ marginLeft: "auto" }}>
              <PhotoUploader onFiles={handleUploadPhotos} compact />
            </div>
          </div>
          {data.photos.length === 0 ? (
            <div style={{
              textAlign: "center", padding: 24, color: "var(--muted)",
              background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10,
            }}>
              <div style={{ fontSize: 32, marginBottom: 6 }}>📷</div>
              Nicio fotografie încă.
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
              {data.photos.map((ph) => {
                const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
                const imgUrl = ph.url?.startsWith("/") ? `${apiBase}${ph.url}` : ph.url;
                const thumbUrl = ph.thumbUrl?.startsWith("/") ? `${apiBase}${ph.thumbUrl}` : ph.thumbUrl;
                return (
                <div
                  key={ph.id ?? ph.filename}
                  title={ph.filename}
                  style={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                    overflow: "hidden",
                  }}
                >
                  <a href={imgUrl} target="_blank" rel="noreferrer" style={{ display: "block" }}>
                    <img
                      src={thumbUrl || imgUrl}
                      alt={ph.filename}
                      loading="lazy"
                      style={{
                        width: "100%", height: 180,
                        objectFit: "cover", display: "block",
                      }}
                    />
                  </a>
                  <div style={{ padding: "6px 10px", fontSize: 11, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {ph.filename}
                    </span>
                    <button
                      onClick={() => ph.id && handleRotate(ph.id, "left")}
                      title="Rotește stânga"
                      style={{ padding: "2px 6px", background: "transparent", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
                    >↺</button>
                    <button
                      onClick={() => ph.id && handleRotate(ph.id, "right")}
                      title="Rotește dreapta"
                      style={{ padding: "2px 6px", background: "transparent", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
                    >↻</button>
                  </div>
                </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function AddPanelForm({ onSubmit }: {
  onSubmit: (p: {
    panelType: string; title: string; widthCm: string; heightCm: string;
    locationInStore: string; notes: string;
  }) => Promise<void>;
}) {
  const [panelType, setPanelType] = useState("panou");
  const [title, setTitle] = useState("");
  const [widthCm, setWidthCm] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [locationInStore, setLocationInStore] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSubmit({ panelType, title, widthCm, heightCm, locationInStore, notes });
      setTitle(""); setWidthCm(""); setHeightCm(""); setLocationInStore(""); setNotes("");
    } finally { setSaving(false); }
  };

  return (
    <details style={{ marginBottom: 20, background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10 }}>
      <summary style={{ padding: "12px 16px", cursor: "pointer", fontWeight: 600, color: "#f59e0b", fontSize: 14 }}>
        ➕ Adaugă Panou / Stand
      </summary>
      <div style={{ padding: "0 16px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <Field label="Tip">
          <select value={panelType} onChange={(e) => setPanelType(e.target.value)} style={inputStyle}>
            {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <Field label="Denumire / Titlu">
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="ex: Panou intrare..." style={inputStyle} />
        </Field>
        <Field label="Lățime (cm)">
          <input type="number" step={0.1} value={widthCm} onChange={(e) => setWidthCm(e.target.value)}
            placeholder="ex: 120" style={inputStyle} />
        </Field>
        <Field label="Înălțime (cm)">
          <input type="number" step={0.1} value={heightCm} onChange={(e) => setHeightCm(e.target.value)}
            placeholder="ex: 80" style={inputStyle} />
        </Field>
        <Field label="Locație în magazin">
          <input type="text" value={locationInStore} onChange={(e) => setLocationInStore(e.target.value)}
            placeholder="ex: Intrare, Raft P3..." style={inputStyle} />
        </Field>
        <Field label="Note">
          <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="Observații..." style={inputStyle} />
        </Field>
        <div style={{ gridColumn: "1 / -1", marginTop: 4 }}>
          <button onClick={handleSave} disabled={saving} style={{
            padding: "9px 20px", borderRadius: 6, border: "none",
            cursor: "pointer", background: "#f59e0b", color: "#000",
            fontWeight: 600, fontSize: 13,
          }}>
            {saving ? "Se salvează…" : "➕ Salvează Panou"}
          </button>
        </div>
      </div>
    </details>
  );
}

function PanelCard({ panel, onDelete, onUpdated }: {
  panel: PanouStandRow; onDelete: () => void; onUpdated: () => Promise<void>;
}) {
  const color = TYPE_COLORS[panel.panelType] || "#6b7280";
  const dims = panel.widthCm && panel.heightCm
    ? `${panel.widthCm} × ${panel.heightCm} cm`
    : panel.widthCm ? `L: ${panel.widthCm} cm`
    : panel.heightCm ? `H: ${panel.heightCm} cm` : "";
  const toast = useToast();

  const handleEdit = async () => {
    const title = window.prompt("Titlu nou:", panel.title || "");
    if (title === null) return;
    const width = window.prompt("Lățime (cm):", panel.widthCm?.toString() || "");
    const height = window.prompt("Înălțime (cm):", panel.heightCm?.toString() || "");
    const location = window.prompt("Locație în magazin:", panel.locationInStore || "");
    const notes = window.prompt("Note:", panel.notes || "");
    try {
      await updatePanel(panel.id, {
        title,
        widthCm: width ? parseFloat(width) : null,
        heightCm: height ? parseFloat(height) : null,
        locationInStore: location || "",
        notes: notes || "",
      });
      toast.success("Actualizat");
      await onUpdated();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  };

  return (
    <div style={{
      background: "var(--card)", border: "1px solid var(--border)",
      borderRadius: 10, padding: 14, borderLeft: `4px solid ${color}`,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13, color }}>
            {TYPE_ICONS[panel.panelType] || ""} {panel.title || TYPE_LABELS[panel.panelType] || panel.panelType}
          </div>
          <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>
            {TYPE_LABELS[panel.panelType] || panel.panelType}
          </div>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={handleEdit} title="Editează" style={{
            padding: "3px 8px", borderRadius: 5, border: "none", cursor: "pointer",
            background: "var(--accent)", color: "#fff", fontSize: 11,
          }}>✏️</button>
          <button onClick={onDelete} title="Șterge" style={{
            padding: "3px 8px", borderRadius: 5, border: "none", cursor: "pointer",
            background: "var(--red)", color: "#fff", fontSize: 11,
          }}>🗑️</button>
        </div>
      </div>
      {dims && (
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          background: "var(--bg-elevated)", padding: "4px 10px",
          borderRadius: 6, marginBottom: 6,
        }}>
          <span style={{ fontSize: 14 }}>📐</span>
          <span style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>{dims}</span>
        </div>
      )}
      {panel.locationInStore && (
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
          📍 {panel.locationInStore}
        </div>
      )}
      {panel.notes && (
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
          📝 {panel.notes}
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ fontSize: 11, color: "var(--muted)", display: "block", marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: 7, borderRadius: 5,
  border: "1px solid var(--border)", background: "var(--bg)",
  color: "var(--text)", fontSize: 13,
};
