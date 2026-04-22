/**
 * Catalog Lunar — port 1:1 din legacy `renderGallery` + `galleryOpenFolder`
 * (gType='catalog') din `adeplast-dashboard/templates/index.html`.
 *
 * Layout legacy:
 *   1. Listare foldere (luni) cu cover image, count poze, buton delete
 *   2. Deschide folder → upload panel (details) + grid de poze cu lightbox
 * Păstrăm convenția `YYYY-MM` / „Luna AAAA" în nume.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  createCatalogFolder,
  deleteCatalogFolder,
  deleteCatalogPhoto,
  getCatalogFolderDetail,
  listCatalogFolders,
  rotateCatalogPhoto,
  uploadCatalogPhoto,
} from "./api";
import type {
  CatalogFolder,
  CatalogPhoto,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
function absUrl(url: string | null | undefined): string {
  if (!url) return "";
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

export default function MktCatalogPage() {
  const toast = useToast();
  const [folders, setFolders] = useState<CatalogFolder[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // state pentru "folder deschis"
  const [openFolderId, setOpenFolderId] = useState<string | null>(null);
  const [openFolderName, setOpenFolderName] = useState<string>("");
  const [openFolderMonth, setOpenFolderMonth] = useState<string | null>(null);
  const [photos, setPhotos] = useState<CatalogPhoto[]>([]);
  const [photosLoading, setPhotosLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);

  // lightbox
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);

  const refreshFolders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listCatalogFolders();
      setFolders(r.folders);
      setNotice(r.notice);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshPhotos = useCallback(
    async (folderId: string) => {
      setPhotosLoading(true);
      try {
        const d = await getCatalogFolderDetail(folderId);
        setPhotos(d.photos);
        setOpenFolderName(d.folderName);
        setOpenFolderMonth(d.month);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Eroare");
      } finally {
        setPhotosLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    refreshFolders();
  }, [refreshFolders]);

  useEffect(() => {
    if (openFolderId) refreshPhotos(openFolderId);
    else setPhotos([]);
  }, [openFolderId, refreshPhotos]);

  // ─── Handlers ───
  async function handleCreateFolder() {
    const name = window.prompt(
      'Numele lunii (ex: „Ianuarie 2026", „2026-01"):',
    );
    if (!name || !name.trim()) return;
    try {
      await createCatalogFolder(name.trim());
      toast.success(`Lună creată: ${name.trim()}`);
      await refreshFolders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleDeleteFolder(f: CatalogFolder, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm(`Ștergi luna „${f.name}" și toate pozele din ea?`))
      return;
    try {
      await deleteCatalogFolder(f.id);
      toast.success("Lună ștearsă");
      if (openFolderId === f.id) setOpenFolderId(null);
      await refreshFolders();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  function handleOpenFolder(f: CatalogFolder) {
    setOpenFolderId(f.id);
    setOpenFolderName(f.name);
    setOpenFolderMonth(f.month);
  }

  function handleBack() {
    setOpenFolderId(null);
    setPhotos([]);
    refreshFolders();
  }

  async function handleUploadFiles(
    source: "camera" | "upload",
    e: React.ChangeEvent<HTMLInputElement>,
  ) {
    if (!openFolderId) return;
    const input = e.target;
    const files = input.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadStatus(
      source === "camera"
        ? "Se salvează..."
        : `Se încarcă ${files.length} fișiere...`,
    );
    let ok = 0;
    let fail = 0;
    for (const file of Array.from(files)) {
      try {
        await uploadCatalogPhoto(openFolderId, file);
        ok++;
      } catch (err) {
        fail++;
        toast.error(
          `${file.name}: ${err instanceof ApiError ? err.message : "eroare"}`,
        );
      }
    }
    if (ok > 0) {
      setUploadStatus(`${ok} poze încărcate!`);
      toast.success(`${ok} poze încărcate`);
    } else {
      setUploadStatus(fail > 0 ? "Eroare la încărcare" : "");
    }
    setUploading(false);
    input.value = "";
    await refreshPhotos(openFolderId);
    // curăță statusul după câteva secunde
    setTimeout(() => setUploadStatus(""), 3000);
  }

  async function handleDeletePhoto(photo: CatalogPhoto, e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm("Ștergi această poză?")) return;
    try {
      await deleteCatalogPhoto(photo.id);
      if (openFolderId) await refreshPhotos(openFolderId);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleRotate(
    photo: CatalogPhoto,
    direction: "left" | "right",
  ) {
    try {
      await rotateCatalogPhoto(photo.id, direction);
      if (openFolderId) await refreshPhotos(openFolderId);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare rotire");
    }
  }

  function openLightbox(idx: number) {
    setLightboxIdx(idx);
  }
  function closeLightbox() {
    setLightboxIdx(null);
  }
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeLightbox();
      if (lightboxIdx == null) return;
      if (e.key === "ArrowRight" && lightboxIdx < photos.length - 1)
        setLightboxIdx(lightboxIdx + 1);
      if (e.key === "ArrowLeft" && lightboxIdx > 0)
        setLightboxIdx(lightboxIdx - 1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxIdx, photos.length]);

  // ────────── Render ──────────

  // ── Ecran „folder deschis" ──
  if (openFolderId) {
    return (
      <div style={styles.page}>
        <div style={styles.headerRow}>
          <button onClick={handleBack} style={styles.backBtn}>
            ← Înapoi
          </button>
          <h1 style={styles.title}>📁 {openFolderName}</h1>
          <span style={styles.subTitle}>
            Catalog Lunar
            {openFolderMonth ? ` · ${openFolderMonth}` : ""}
          </span>
        </div>

        {/* Upload panel (details open/close) */}
        <details style={styles.uploadPanel}>
          <summary style={styles.uploadSummary}>📤 Încarcă Poze Noi</summary>
          <div style={styles.uploadBody}>
            <div style={styles.uploadButtons}>
              <label style={styles.cameraBtn}>
                📷 Fotografiază
                <input
                  ref={cameraInput}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  style={{ display: "none" }}
                  onChange={(e) => handleUploadFiles("camera", e)}
                />
              </label>
              <label style={styles.uploadBtn}>
                📥 Alege Fișiere
                <input
                  ref={fileInput}
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  multiple
                  style={{ display: "none" }}
                  onChange={(e) => handleUploadFiles("upload", e)}
                />
              </label>
              <span style={styles.uploadStatus}>
                {uploading ? "⏳ " : ""}
                {uploadStatus}
              </span>
            </div>
            <div style={styles.uploadHint}>
              max 15 MB per poză · JPEG/PNG/GIF/WebP
            </div>
          </div>
        </details>

        {/* Photo grid */}
        {photosLoading ? (
          <div style={styles.loading}>Se încarcă…</div>
        ) : photos.length === 0 ? (
          <div style={styles.empty}>
            Nu există poze. Deschide panoul de mai sus și încarcă câteva!
          </div>
        ) : (
          <div style={styles.photoGrid}>
            {photos.map((img, idx) => (
              <div key={img.id} style={styles.photoCard}>
                <img
                  src={absUrl(img.thumbUrl)}
                  loading="lazy"
                  onClick={() => openLightbox(idx)}
                  style={styles.photoThumb}
                  alt={img.filename}
                />
                <div style={styles.photoMeta}>
                  <div style={styles.photoMetaLine}>
                    <span style={styles.photoFilename} title={img.filename}>
                      {img.filename}
                    </span>
                  </div>
                  <div style={styles.photoFooter}>
                    <span style={styles.photoSize}>
                      {img.uploadedAt?.slice(0, 10)} · {img.sizeKb} KB
                    </span>
                    <button
                      onClick={(e) => handleDeletePhoto(img, e)}
                      style={styles.photoDelete}
                      title="Șterge"
                    >
                      🗑
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Lightbox */}
        {lightboxIdx != null && photos[lightboxIdx] && (
          <div
            style={styles.lightboxOverlay}
            onClick={closeLightbox}
          >
            <div
              style={styles.lightboxControls}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => handleRotate(photos[lightboxIdx], "left")}
                style={styles.lightboxRotate}
                title="Rotește stânga 90°"
              >
                ↺ 90°
              </button>
              <button
                onClick={() => handleRotate(photos[lightboxIdx], "right")}
                style={styles.lightboxRotate}
                title="Rotește dreapta 90°"
              >
                ↻ 90°
              </button>
              <a
                href={absUrl(photos[lightboxIdx].url)}
                download={photos[lightboxIdx].filename}
                style={styles.lightboxDownload}
              >
                ⬇ Download
              </a>
              <button onClick={closeLightbox} style={styles.lightboxClose}>
                ✕
              </button>
            </div>
            <img
              src={absUrl(photos[lightboxIdx].url)}
              style={styles.lightboxImg}
              onClick={(e) => e.stopPropagation()}
              alt={photos[lightboxIdx].filename}
            />
            <div
              style={styles.lightboxCaption}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ fontWeight: 600 }}>
                {photos[lightboxIdx].filename}
              </div>
              <div style={{ fontSize: 11, color: "#888", marginTop: 4 }}>
                {photos[lightboxIdx].sizeKb} KB
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Ecran „listă foldere (luni)" ──
  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>📖 Catalog Lunar</h1>
      </div>

      <div style={styles.toolbar}>
        <button onClick={handleCreateFolder} style={styles.primaryBtn}>
          ➕ Lună Nouă
        </button>
        <span style={styles.toolbarHint}>
          Click pe o lună pentru a deschide
        </span>
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}
      {notice && !loading && folders.length === 0 && (
        <div style={styles.notice}>{notice}</div>
      )}

      {loading ? (
        <div style={styles.loading}>Se încarcă…</div>
      ) : folders.length === 0 ? (
        <div style={styles.empty}>
          Nu există luni. Creează una nouă (buton „➕ Lună Nouă").
        </div>
      ) : (
        <div style={styles.folderGrid}>
          {folders.map((f) => {
            const hasCover = Boolean(f.coverUrl);
            return (
              <div
                key={f.id}
                onClick={() => handleOpenFolder(f)}
                style={styles.folderCard}
                onMouseOver={(e) =>
                  (e.currentTarget.style.borderColor = "var(--cyan)")
                }
                onMouseOut={(e) =>
                  (e.currentTarget.style.borderColor = "var(--border)")
                }
              >
                <div
                  style={{
                    ...styles.folderCover,
                    ...(hasCover
                      ? {
                          backgroundImage: `url('${absUrl(f.coverUrl)}')`,
                          backgroundSize: "cover",
                          backgroundPosition: "center",
                        }
                      : { fontSize: 50 }),
                  }}
                >
                  {hasCover ? "" : "📁"}
                </div>
                <div style={styles.folderBody}>
                  <div style={styles.folderName}>{f.name}</div>
                  <div style={styles.folderCount}>
                    {f.photoCount} {f.photoCount === 1 ? "poză" : "poze"}
                    {f.month ? ` · ${f.month}` : ""}
                  </div>
                  <button
                    onClick={(e) => handleDeleteFolder(f, e)}
                    style={styles.folderDelete}
                  >
                    🗑 Șterge
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 12px", color: "var(--text)", maxWidth: 1200, margin: "0 auto" },
  headerRow: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 17,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: -0.2,
  },
  subTitle: { color: "var(--muted)", fontSize: 13 },
  backBtn: {
    padding: "6px 14px",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--card)",
    color: "var(--text)",
    cursor: "pointer",
  },
  toolbar: {
    display: "flex",
    gap: 10,
    marginBottom: 20,
    flexWrap: "wrap",
    alignItems: "center",
  },
  toolbarHint: { color: "var(--muted)", fontSize: 13 },
  primaryBtn: {
    padding: "8px 18px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    background: "var(--cyan)",
    color: "#000",
    fontWeight: 600,
  },
  errorBox: {
    color: "var(--red)",
    padding: 12,
    background: "rgba(220, 38, 38, 0.08)",
    borderRadius: 6,
    marginBottom: 12,
  },
  notice: {
    padding: "8px 12px",
    marginBottom: 12,
    background: "var(--accent-soft)",
    color: "var(--text)",
    borderRadius: 6,
    fontSize: 13,
    border: "1px solid var(--border)",
  },
  loading: { color: "var(--muted)", padding: 12 },
  empty: {
    color: "var(--muted)",
    textAlign: "center",
    padding: 40,
    gridColumn: "1 / -1",
  },

  // folder grid
  folderGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 16,
  },
  folderCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    cursor: "pointer",
    overflow: "hidden",
    transition: "all .2s",
  },
  folderCover: {
    background: "var(--bg)",
    height: 120,
    borderRadius: "10px 10px 0 0",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  folderBody: { padding: 12, textAlign: "center" as const },
  folderName: { fontWeight: 600, marginBottom: 4 },
  folderCount: { color: "var(--muted)", fontSize: 13 },
  folderDelete: {
    marginTop: 8,
    padding: "4px 12px",
    borderRadius: 6,
    border: "1px solid var(--red)",
    background: "transparent",
    color: "var(--red)",
    cursor: "pointer",
    fontSize: 12,
  },

  // upload panel
  uploadPanel: {
    marginBottom: 20,
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
  },
  uploadSummary: {
    padding: "14px 18px",
    cursor: "pointer",
    fontWeight: 600,
    color: "var(--cyan)",
    fontSize: 15,
  },
  uploadBody: {
    padding: "0 18px 18px",
  },
  uploadButtons: {
    display: "flex",
    gap: 10,
    alignItems: "center",
    flexWrap: "wrap",
  },
  cameraBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    background: "#25D366",
    color: "#fff",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 15,
  },
  uploadBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    background: "var(--cyan)",
    color: "#000",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 15,
  },
  uploadStatus: {
    color: "var(--muted)",
    fontSize: 13,
    marginLeft: "auto",
  },
  uploadHint: { color: "var(--muted)", fontSize: 11, marginTop: 6 },

  // photo grid
  photoGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 14,
  },
  photoCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    overflow: "hidden",
  },
  photoThumb: {
    width: "100%",
    height: 180,
    objectFit: "cover",
    cursor: "pointer",
    display: "block",
  },
  photoMeta: { padding: 10 },
  photoMetaLine: {
    fontSize: 11,
    color: "var(--muted)",
    marginBottom: 4,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  photoFilename: { color: "var(--cyan)" },
  photoFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  photoSize: { fontSize: 10, color: "var(--muted)" },
  photoDelete: {
    padding: "3px 8px",
    borderRadius: 5,
    border: "none",
    cursor: "pointer",
    background: "var(--red)",
    color: "#fff",
    fontSize: 11,
  },

  // lightbox
  lightboxOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    background: "rgba(0,0,0,0.92)",
    zIndex: 10000,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "column",
    cursor: "pointer",
  },
  lightboxControls: {
    position: "absolute",
    top: 16,
    right: 24,
    display: "flex",
    gap: 10,
    zIndex: 10001,
  },
  lightboxDownload: {
    padding: "8px 16px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    background: "var(--cyan)",
    color: "#000",
    fontWeight: 600,
    fontSize: 14,
    textDecoration: "none",
    display: "inline-flex",
    alignItems: "center",
  },
  lightboxClose: {
    padding: "8px 16px",
    borderRadius: 8,
    border: "none",
    cursor: "pointer",
    background: "var(--red)",
    color: "#fff",
    fontWeight: 600,
    fontSize: 14,
  },
  lightboxRotate: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.3)",
    cursor: "pointer",
    background: "rgba(0,0,0,0.5)",
    color: "#fff",
    fontWeight: 600,
    fontSize: 14,
  },
  lightboxImg: {
    maxWidth: "92vw",
    maxHeight: "80vh",
    borderRadius: 8,
    boxShadow: "0 0 40px rgba(0,0,0,0.5)",
  },
  lightboxCaption: {
    color: "#ccc",
    marginTop: 12,
    fontSize: 13,
    textAlign: "center",
    maxWidth: 600,
  },
};
