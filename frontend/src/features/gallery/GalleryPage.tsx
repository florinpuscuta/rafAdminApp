import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch } from "../../shared/api";
import { PhotoUploader } from "../../shared/ui/PhotoUploader";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  createFolder,
  deleteFolder,
  deletePhoto,
  listFolders,
  listPhotos,
  uploadPhoto,
} from "./api";
import type { FolderType, GalleryFolder, GalleryPhoto } from "./types";

const TYPE_LABELS: Record<FolderType, string> = {
  magazine: "Magazine",
  catalog: "Catalog",
  competition: "Concurență",
  other: "Alte",
};
const TYPES: FolderType[] = ["magazine", "catalog", "competition"];

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

type TypeSummary = Record<FolderType, { folders: number; photos: number }>;

export default function GalleryPage() {
  const toast = useToast();
  const [activeType, setActiveType] = useState<FolderType>("magazine");
  const [folders, setFolders] = useState<GalleryFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [photos, setPhotos] = useState<GalleryPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Cache-buster per poză — incrementat la rotație pentru a forța reload <img>
  const [photoBust, setPhotoBust] = useState<Record<string, number>>({});
  const [newFolderName, setNewFolderName] = useState("");
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [summary, setSummary] = useState<TypeSummary>({
    magazine: { folders: 0, photos: 0 },
    catalog: { folders: 0, photos: 0 },
    competition: { folders: 0, photos: 0 },
    other: { folders: 0, photos: 0 },
  });

  // Summary — totalizare peste toate tipurile (o singură dată la mount +
  // după orice mutație).
  const refreshSummary = useCallback(async () => {
    try {
      const entries = await Promise.all(
        TYPES.map(async (t) => {
          const list = await listFolders(t);
          const photosTotal = list.reduce((acc, f) => acc + (f.photoCount || 0), 0);
          return [t, { folders: list.length, photos: photosTotal }] as const;
        }),
      );
      setSummary(Object.fromEntries(entries) as TypeSummary);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { refreshSummary(); }, [refreshSummary]);

  const refreshFolders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listFolders(activeType);
      setFolders(list);
      if (list.length > 0 && !list.find((f) => f.id === selectedFolderId)) {
        setSelectedFolderId(list[0].id);
      } else if (list.length === 0) {
        setSelectedFolderId(null);
        setPhotos([]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, [activeType, selectedFolderId]);

  const refreshPhotos = useCallback(async (folderId: string | null) => {
    if (!folderId) {
      setPhotos([]);
      return;
    }
    try {
      setPhotos(await listPhotos(folderId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    }
  }, []);

  useEffect(() => {
    refreshFolders();
  }, [activeType, refreshFolders]);

  useEffect(() => {
    refreshPhotos(selectedFolderId);
  }, [selectedFolderId, refreshPhotos]);

  async function handleCreateFolder(e: React.FormEvent) {
    e.preventDefault();
    if (!newFolderName.trim()) {
      setCreatingFolder(false);
      return;
    }
    try {
      const folder = await createFolder({ type: activeType, name: newFolderName.trim() });
      setNewFolderName("");
      setCreatingFolder(false);
      toast.success(`Folder creat: ${folder.name}`);
      setSelectedFolderId(folder.id);
      await refreshFolders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleDeleteFolder(folder: GalleryFolder) {
    if (!window.confirm(`Șterge folderul "${folder.name}" și toate fotografiile din el?`))
      return;
    try {
      await deleteFolder(folder.id);
      toast.success("Folder șters");
      await refreshFolders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleUpload(files: FileList) {
    if (!files || files.length === 0 || !selectedFolderId) return;
    setUploading(true);
    let ok = 0;
    let fail = 0;
    for (const file of Array.from(files)) {
      try {
        await uploadPhoto(selectedFolderId, file);
        ok++;
      } catch (err) {
        fail++;
        toast.error(
          `${file.name}: ${err instanceof ApiError ? err.message : "eroare"}`,
        );
      }
    }
    if (ok > 0) toast.success(`${ok} fotografii încărcate`);
    setUploading(false);
    await Promise.all([refreshPhotos(selectedFolderId), refreshFolders(), refreshSummary()]);
    void fail;
  }

  async function handleRotate(photoId: string, direction: "left" | "right") {
    try {
      await apiFetch(`/api/gallery/photos/${photoId}/rotate?direction=${direction}`, {
        method: "POST",
      });
      // Incrementăm cache-buster pentru această poză → <img src> se reîncarcă
      setPhotoBust((m) => ({ ...m, [photoId]: Date.now() }));
      await refreshPhotos(selectedFolderId);
      toast.success("Rotită");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare rotire");
    }
  }

  async function handleDeletePhoto(photo: GalleryPhoto) {
    if (!window.confirm("Șterge fotografia?")) return;
    try {
      await deletePhoto(photo.id);
      await Promise.all([refreshPhotos(selectedFolderId), refreshFolders()]);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  const totalFolders = Object.values(summary).reduce((a, s) => a + s.folders, 0);
  const totalPhotos = Object.values(summary).reduce((a, s) => a + s.photos, 0);
  const TYPE_COLORS: Record<FolderType, string> = {
    magazine: "#3b82f6",
    catalog: "#f59e0b",
    competition: "#ef4444",
    other: "#8b5cf6",
  };

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>📸 Galerie</h2>

      {/* Sumar — total + per tip */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
        gap: 10, marginBottom: 16,
      }}>
        <div style={{
          padding: 14, background: "linear-gradient(135deg,#22c55e22,#22c55e11)",
          border: "1px solid #22c55e44", borderRadius: 10, textAlign: "center",
        }}>
          <div style={{ fontSize: 26, fontWeight: 800, color: "#22c55e" }}>{totalPhotos}</div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
            Total fotografii · {totalFolders} foldere
          </div>
        </div>
        {TYPES.map((t) => {
          const c = TYPE_COLORS[t];
          const s = summary[t];
          return (
            <div
              key={t}
              onClick={() => { setActiveType(t); setSelectedFolderId(null); }}
              style={{
                padding: 14,
                background: `linear-gradient(135deg,${c}22,${c}11)`,
                border: `1px solid ${c}44`,
                borderRadius: 10, textAlign: "center", cursor: "pointer",
                outline: activeType === t ? `2px solid ${c}` : "none",
              }}
            >
              <div style={{ fontSize: 22, fontWeight: 700, color: c }}>{s.photos}</div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                {TYPE_LABELS[t]} · {s.folders} foldere
              </div>
            </div>
          );
        })}
      </div>

      <div style={styles.tabs}>
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => {
              setActiveType(t);
              setSelectedFolderId(null);
            }}
            style={{
              ...styles.tab,
              ...(t === activeType ? styles.tabActive : {}),
            }}
          >
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {/* Action bar — 3 butoane: Fotografiază, Alege, Folder nou */}
      <div style={styles.actionBar}>
        {creatingFolder ? (
          <form
            onSubmit={handleCreateFolder}
            style={{ display: "flex", gap: 8, flex: 1, alignItems: "center" }}
          >
            <input
              autoFocus
              placeholder="Denumire folder..."
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              style={{
                flex: 1, padding: "8px 12px", fontSize: 13,
                border: "1px solid var(--border)", borderRadius: 8,
                background: "var(--bg)", color: "var(--text)", minWidth: 0,
              }}
            />
            <button
              type="submit"
              style={{
                padding: "8px 12px", background: "var(--green)", color: "#fff",
                border: "none", borderRadius: 8, cursor: "pointer",
                fontWeight: 700, minHeight: 36, whiteSpace: "nowrap",
              }}
            >✓</button>
            <button
              type="button"
              onClick={() => { setCreatingFolder(false); setNewFolderName(""); }}
              style={{
                padding: "8px 12px", background: "var(--card)", color: "var(--muted)",
                border: "1px solid var(--border)", borderRadius: 8, cursor: "pointer",
                minHeight: 36,
              }}
            >✗</button>
          </form>
        ) : (
          <div style={{ display: "flex", gap: 8, flex: 1, alignItems: "stretch" }}>
            <div style={{ flex: 2, minWidth: 0, opacity: selectedFolderId ? 1 : 0.55 }}>
              <PhotoUploader
                onFiles={handleUpload}
                disabled={!selectedFolderId || uploading}
                status={uploading ? "Se încarcă…" : undefined}
              />
            </div>
            <button
              type="button"
              onClick={() => setCreatingFolder(true)}
              style={{
                flex: "1 1 0", padding: "8px 12px",
                background: "var(--card)", color: "var(--text)",
                border: "1px dashed var(--border)", borderRadius: 8,
                cursor: "pointer", fontSize: 13, fontWeight: 600,
                minHeight: 36, whiteSpace: "nowrap", minWidth: 0,
              }}
              title="Creează folder nou"
            >
              📁+ Folder
            </button>
          </div>
        )}
      </div>

      <div style={styles.layout}>
        <aside style={styles.sidebar}>
          {loading && folders.length === 0 ? (
            <p style={{ color: "#888", fontSize: 13 }}>Se încarcă…</p>
          ) : folders.length === 0 ? (
            <p style={{ color: "#888", fontSize: 13 }}>Niciun folder. Creează unul.</p>
          ) : (
            folders.map((f) => {
              const isSel = f.id === selectedFolderId;
              return (
                <div
                  key={f.id}
                  onClick={() => setSelectedFolderId(f.id)}
                  style={{
                    ...styles.folderItem,
                    ...(isSel ? styles.folderActive : {}),
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: isSel ? 600 : 400 }}>
                      {f.name}
                    </div>
                    <div style={{ fontSize: 11, color: "#888", display: "flex", gap: 8 }}>
                      <span>{f.photoCount} foto</span>
                      {f.createdAt && (
                        <span title={`Creat la ${fmtDateTime(f.createdAt)}`}>
                          · {fmtDateShort(f.createdAt)}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteFolder(f);
                    }}
                    style={styles.deleteBtn}
                    title="Șterge folder"
                  >
                    ×
                  </button>
                </div>
              );
            })
          )}
        </aside>

        <main style={styles.main}>
          {selectedFolderId ? (
            <>
              {photos.length === 0 ? (
                <p style={{ color: "#888" }}>Niciun photo încă.</p>
              ) : (
                <div style={styles.grid}>
                  {photos.map((p) => {
                    const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
                    const baseUrl = p.url?.startsWith("/") ? `${apiBase}${p.url}` : p.url;
                    const bust = photoBust[p.id];
                    const imgUrl = bust && baseUrl
                      ? `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}v=${bust}`
                      : baseUrl;
                    return (
                    <div key={p.id} style={styles.photoCard}>
                      <a href={imgUrl} target="_blank" rel="noreferrer">
                        <img src={imgUrl} alt={p.filename} style={styles.thumb} />
                      </a>
                      <div style={styles.photoMeta}>
                        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                          <span style={styles.filename} title={p.filename}>
                            {p.filename}
                          </span>
                          {p.uploadedAt && (
                            <span style={{ fontSize: 11, color: "var(--muted)" }} title={`Intrat în DB la ${fmtDateTime(p.uploadedAt)}`}>
                              📅 {fmtDateTime(p.uploadedAt)}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => handleRotate(p.id, "left")}
                          style={styles.photoAction}
                          title="Rotește stânga 90°"
                        >
                          ↺
                        </button>
                        <button
                          onClick={() => handleRotate(p.id, "right")}
                          style={styles.photoAction}
                          title="Rotește dreapta 90°"
                        >
                          ↻
                        </button>
                        <button
                          onClick={() => handleDeletePhoto(p)}
                          style={styles.photoDelete}
                          title="Șterge"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            <p style={{ color: "#888" }}>Selectează sau creează un folder.</p>
          )}
        </main>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  tabs: { display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid #eee" },
  tab: {
    padding: "8px 14px",
    fontSize: 13,
    cursor: "pointer",
    background: "transparent",
    border: "none",
    borderBottom: "2px solid transparent",
  },
  tabActive: { borderBottom: "2px solid #2563eb", fontWeight: 600, color: "#2563eb" },
  actionBar: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    padding: 10,
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    marginBottom: 12,
  },
  layout: {
    display: "grid",
    gridTemplateColumns: "220px 1fr",
    gap: 16,
    height: "calc(100vh - 280px)",
    minHeight: 400,
  },
  sidebar: {
    padding: 8,
    border: "1px solid #eee",
    borderRadius: 6,
    background: "#fff",
    display: "flex",
    flexDirection: "column",
    gap: 4,
    overflowY: "auto",
    minHeight: 0,
    maxHeight: 130,
  },
  newFolder: { display: "flex", gap: 4, marginBottom: 10 },
  input: { flex: 1, padding: 6, fontSize: 13, border: "1px solid #ccc", borderRadius: 4 },
  btn: { padding: "4px 10px", fontSize: 14, cursor: "pointer" },
  folderItem: {
    display: "flex",
    alignItems: "center",
    padding: "6px 8px",
    borderRadius: 4,
    cursor: "pointer",
    gap: 4,
  },
  folderActive: { background: "#eff6ff" },
  deleteBtn: {
    padding: "2px 8px",
    fontSize: 14,
    cursor: "pointer",
    background: "transparent",
    border: "none",
    color: "#b00020",
  },
  main: {
    padding: 16,
    border: "1px solid #eee",
    borderRadius: 6,
    background: "#fff",
    overflowY: "auto",
    minHeight: 0,
  },
  uploadBar: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: 10,
    background: "#fafafa",
    border: "1px dashed #ccc",
    borderRadius: 6,
    marginBottom: 16,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
    gap: 12,
  },
  photoCard: {
    border: "1px solid #eee",
    borderRadius: 6,
    overflow: "hidden",
    background: "#fff",
  },
  thumb: {
    width: "100%",
    height: 180,
    objectFit: "cover",
    display: "block",
    background: "#f8fafc",
  },
  photoMeta: {
    display: "flex",
    alignItems: "center",
    padding: "6px 10px",
    gap: 4,
    fontSize: 12,
  },
  filename: {
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  photoDelete: {
    padding: "2px 8px",
    cursor: "pointer",
    background: "transparent",
    border: "none",
    color: "#b00020",
  },
  photoAction: {
    padding: "2px 8px",
    cursor: "pointer",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 4,
    color: "var(--text)",
    fontSize: 14,
  },
};
