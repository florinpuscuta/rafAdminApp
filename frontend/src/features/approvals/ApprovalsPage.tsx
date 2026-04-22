import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { useConfirm } from "../../shared/ui/ConfirmDialog";
import { useToast } from "../../shared/ui/ToastProvider";
import { approvePhoto, listPending, rejectPhoto, type PendingPhoto } from "./api";

const TYPE_LABELS: Record<string, string> = {
  panouri: "Panouri",
  magazine: "Magazine",
  concurenta: "Concurență",
  catalog: "Catalog",
  problems: "Probleme",
};
const TYPE_COLORS: Record<string, string> = {
  panouri: "#f59e0b",
  magazine: "#3b82f6",
  concurenta: "#ef4444",
  catalog: "#22c55e",
  problems: "#8b5cf6",
};

export default function ApprovalsPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [photos, setPhotos] = useState<PendingPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("");

  const refresh = useCallback(() => {
    setLoading(true);
    listPending()
      .then((rows) => { setPhotos(rows); setError(null); })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Eroare"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleApprove(p: PendingPhoto) {
    try {
      await approvePhoto(p.id);
      toast.success(`Aprobat: ${p.filename}`);
      setPhotos((prev) => prev.filter((x) => x.id !== p.id));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la aprobare");
    }
  }

  async function handleReject(p: PendingPhoto) {
    const ok = await confirm({
      title: "Respinge poza?",
      message: `Poza "${p.filename}" va fi ștearsă definitiv.`,
      confirmLabel: "Respinge",
      danger: true,
    });
    if (!ok) return;
    try {
      await rejectPhoto(p.id);
      toast.success("Respinsă și ștearsă");
      setPhotos((prev) => prev.filter((x) => x.id !== p.id));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la respingere");
    }
  }

  async function handleBulkApprove() {
    const visible = filtered;
    if (visible.length === 0) return;
    const ok = await confirm({
      title: `Aprobă ${visible.length} poze?`,
      message: "Toate pozele filtrate vor deveni vizibile tuturor.",
      confirmLabel: "Aprobă toate",
    });
    if (!ok) return;
    let done = 0, failed = 0;
    for (const p of visible) {
      try { await approvePhoto(p.id); done++; }
      catch { failed++; }
    }
    toast.success(`Aprobate: ${done}${failed ? ` (${failed} eșec)` : ""}`);
    refresh();
  }

  const filtered = typeFilter
    ? photos.filter((p) => p.folder_type === typeFilter)
    : photos;

  const counts = photos.reduce<Record<string, number>>((acc, p) => {
    acc[p.folder_type] = (acc[p.folder_type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ padding: "4px 4px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>
          ✓ Aprobări Poze
        </h1>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          {photos.length} în așteptare
        </span>
        <button
          type="button"
          onClick={refresh}
          style={{
            marginLeft: "auto",
            padding: "6px 12px",
            fontSize: 13,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            cursor: "pointer",
            color: "var(--text)",
          }}
        >
          ⟲ Reîncarcă
        </button>
      </div>

      {photos.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
          <FilterChip
            label="Toate" count={photos.length} color="var(--text)"
            active={!typeFilter} onClick={() => setTypeFilter("")}
          />
          {Object.entries(counts).sort().map(([t, n]) => (
            <FilterChip
              key={t}
              label={TYPE_LABELS[t] || t} count={n}
              color={TYPE_COLORS[t] || "var(--accent)"}
              active={typeFilter === t}
              onClick={() => setTypeFilter(t)}
            />
          ))}
          <button
            type="button"
            onClick={handleBulkApprove}
            style={{
              marginLeft: "auto",
              padding: "6px 12px",
              fontSize: 12,
              background: "var(--green)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            ✓ Aprobă toate ({filtered.length})
          </button>
        </div>
      )}

      {loading && <div style={{ color: "var(--muted)", padding: 20 }}>Se încarcă…</div>}
      {error && <div style={{ color: "var(--red)", padding: 12 }}>{error}</div>}
      {!loading && photos.length === 0 && (
        <div style={{
          padding: 40, textAlign: "center",
          background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10,
          color: "var(--muted)",
        }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>✓</div>
          Nicio poză în așteptare. Toate sunt aprobate.
        </div>
      )}

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: 10,
      }}>
        {filtered.map((p) => (
          <PhotoCard key={p.id} photo={p} onApprove={handleApprove} onReject={handleReject} />
        ))}
      </div>
    </div>
  );
}

function FilterChip({
  label, count, color, active, onClick,
}: {
  label: string; count: number; color: string; active: boolean; onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "5px 10px",
        fontSize: 12,
        borderRadius: 16,
        border: `1px solid ${active ? color : "var(--border)"}`,
        background: active ? `${color}22` : "var(--card)",
        color: active ? color : "var(--text)",
        cursor: "pointer",
        fontWeight: active ? 700 : 500,
      }}
    >
      {label} <span style={{ opacity: 0.7 }}>({count})</span>
    </button>
  );
}

function PhotoCard({
  photo, onApprove, onReject,
}: {
  photo: PendingPhoto;
  onApprove: (p: PendingPhoto) => void;
  onReject: (p: PendingPhoto) => void;
}) {
  const color = TYPE_COLORS[photo.folder_type] || "var(--accent)";
  const typeLabel = TYPE_LABELS[photo.folder_type] || photo.folder_type;
  return (
    <div style={{
      background: "var(--card)",
      border: "1px solid var(--border)",
      borderRadius: 10,
      overflow: "hidden",
      display: "flex",
      flexDirection: "column",
    }}>
      <div style={{ position: "relative", paddingTop: "100%", background: "#000" }}>
        <img
          src={photo.url}
          alt={photo.filename}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
          loading="lazy"
        />
        <div style={{
          position: "absolute",
          top: 6,
          left: 6,
          background: `${color}dd`,
          color: "#fff",
          padding: "2px 8px",
          borderRadius: 10,
          fontSize: 10,
          fontWeight: 700,
          textTransform: "uppercase",
        }}>
          {typeLabel}
        </div>
      </div>
      <div style={{ padding: "6px 8px", fontSize: 11, color: "var(--text)", lineHeight: 1.3 }}>
        <div style={{ fontWeight: 600, wordBreak: "break-word" }}>{photo.folder_name}</div>
        <div style={{ color: "var(--muted)", fontSize: 10, marginTop: 2 }}>
          {new Date(photo.uploaded_at).toLocaleDateString("ro-RO")}
        </div>
      </div>
      <div style={{ display: "flex", borderTop: "1px solid var(--border)" }}>
        <button
          type="button"
          onClick={() => onReject(photo)}
          style={{
            flex: 1,
            padding: "8px 4px",
            border: "none",
            borderRight: "1px solid var(--border)",
            background: "transparent",
            color: "var(--red)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          ✗ Respinge
        </button>
        <button
          type="button"
          onClick={() => onApprove(photo)}
          style={{
            flex: 1,
            padding: "8px 4px",
            border: "none",
            background: "transparent",
            color: "var(--green)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          ✓ Aprobă
        </button>
      </div>
    </div>
  );
}
