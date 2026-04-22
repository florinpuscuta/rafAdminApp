/**
 * Acțiuni Concurență — port din legacy `renderConcurenta` (gType='concurenta').
 * Vedere anuală cu 12 celule lunare; click pe o lună deschide uploader + grid.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { useConfirm } from "../../shared/ui/ConfirmDialog";
import {
  deleteConcurentaPhoto,
  ensureConcurentaFolder,
  getConcurentaPhotos,
  getConcurentaYear,
  rotateConcurentaPhoto,
  uploadConcurentaPhotos,
} from "./api";
import type {
  ConcurentaMonthCell,
  ConcurentaPhotoOut,
} from "./types";

export default function MktConcurentaPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;
  const [year, setYear] = useState(currentYear);
  const [cells, setCells] = useState<ConcurentaMonthCell[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openFolder, setOpenFolder] = useState<string | null>(null);
  const [photos, setPhotos] = useState<ConcurentaPhotoOut[]>([]);

  const loadYear = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getConcurentaYear(year);
      setCells(r.cells || []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => { loadYear(); }, [loadYear]);

  const loadFolderPhotos = useCallback(async (folderKey: string) => {
    try {
      const r = await getConcurentaPhotos(folderKey);
      setPhotos(r.images || []);
      setOpenFolder(folderKey);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  }, [toast]);

  const handleOpenMonth = async (cell: ConcurentaMonthCell) => {
    if (!cell.folderId) {
      // Creează folder automat dacă nu există (parity cu legacy os.makedirs)
      try {
        await ensureConcurentaFolder(year, cell.month);
        await loadYear();
      } catch (e) {
        toast.error(e instanceof ApiError ? e.message : "Eroare");
        return;
      }
    }
    await loadFolderPhotos(cell.folderKey);
  };

  const handleUpload = async (folderKey: string, files: FileList) => {
    try {
      const r = await uploadConcurentaPhotos(folderKey, files);
      toast.success(`${r.uploaded ?? files.length} poze încărcate`);
      await loadFolderPhotos(folderKey);
      await loadYear();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare la upload");
    }
  };

  const handleDeletePhoto = async (photo: ConcurentaPhotoOut) => {
    const ok = await confirm({
      title: "Ștergi poza?",
      message: photo.filename,
      danger: true,
    });
    if (!ok) return;
    try {
      await deleteConcurentaPhoto(photo.id);
      if (openFolder) await loadFolderPhotos(openFolder);
      await loadYear();
      toast.success("Ștearsă");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  };

  const handleRotate = async (photo: ConcurentaPhotoOut) => {
    try {
      await rotateConcurentaPhoto(photo.id);
      if (openFolder) await loadFolderPhotos(openFolder);
      toast.success("Rotită");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    }
  };

  const yearOptions = useMemo(() => {
    return [currentYear + 1, currentYear, currentYear - 1, currentYear - 2];
  }, [currentYear]);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>🎯 Acțiuni Concurență</h1>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))} style={styles.select}>
          {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {loading && <div style={styles.loading}>Se încarcă…</div>}

      {!loading && (
        <div style={styles.grid}>
          {cells
            .filter((c) => c.count > 0 || (year === currentYear && c.month === currentMonth))
            .map((c) => (
              <MonthCard key={c.month} cell={c} onOpen={() => handleOpenMonth(c)} />
            ))}
        </div>
      )}

      {openFolder && (
        <FolderDetail
          folderKey={openFolder}
          photos={photos}
          onClose={() => { setOpenFolder(null); setPhotos([]); }}
          onUpload={(files) => handleUpload(openFolder, files)}
          onDelete={handleDeletePhoto}
          onRotate={handleRotate}
        />
      )}
    </div>
  );
}

function MonthCard({ cell, onOpen }: { cell: ConcurentaMonthCell; onOpen: () => void }) {
  const empty = cell.count === 0;
  return (
    <div
      onClick={cell.isFuture ? undefined : onOpen}
      style={{
        background: "var(--card)", border: "1px solid var(--border)",
        borderRadius: 10, overflow: "hidden",
        cursor: cell.isFuture ? "default" : "pointer",
        opacity: cell.isFuture ? 0.4 : 1,
      }}
    >
      <div style={{
        height: 120, background: cell.coverUrl
          ? `url(${cell.coverUrl}) center/cover`
          : "var(--bg-elevated)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        {!cell.coverUrl && <div style={{ fontSize: 32 }}>📷</div>}
      </div>
      <div style={{ padding: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 13 }}>{cell.label}</div>
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
          {empty ? "Fără poze" : `${cell.count} poze`}
        </div>
      </div>
    </div>
  );
}

function FolderDetail({
  folderKey, photos, onClose, onUpload, onDelete, onRotate,
}: {
  folderKey: string;
  photos: ConcurentaPhotoOut[];
  onClose: () => void;
  onUpload: (files: FileList) => void;
  onDelete: (photo: ConcurentaPhotoOut) => void;
  onRotate: (photo: ConcurentaPhotoOut) => void;
}) {
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <button onClick={onClose} style={styles.btnSecondary}>← Închide</button>
        <h3 style={{ margin: 0, color: "var(--accent)" }}>{folderKey}</h3>
        <label style={{ ...styles.btnPrimary, marginLeft: "auto" }}>
          📤 Încarcă poze
          <input type="file" multiple accept="image/*" style={{ display: "none" }}
            onChange={(e) => e.target.files && onUpload(e.target.files)} />
        </label>
      </div>

      {photos.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: "var(--muted)" }}>
          Nicio poză încă. Folosește butonul de mai sus.
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
          {photos.map((p) => (
            <div key={p.id} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
              <img src={p.thumbUrl || p.url} alt={p.filename} style={{ width: "100%", height: 160, objectFit: "cover", display: "block" }} />
              <div style={{ padding: 8, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 11 }}>
                <span style={{ color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.filename}</span>
                <div style={{ display: "flex", gap: 4 }}>
                  <button onClick={() => onRotate(p)} style={styles.iconBtn} title="Rotește">↻</button>
                  <button onClick={() => onDelete(p)} style={{ ...styles.iconBtn, color: "var(--red)" }} title="Șterge">🗑️</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 20px", color: "var(--text)" },
  headerRow: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" },
  title: { margin: 0, fontSize: 18, fontWeight: 600, color: "var(--text)" },
  select: { padding: "6px 10px", background: "var(--bg-elevated)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 13 },
  error: { color: "var(--red)", padding: 12, background: "rgba(220,38,38,0.08)", borderRadius: 6, marginBottom: 12 },
  loading: { color: "var(--muted)", padding: 20 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 },
  btnPrimary: { padding: "8px 16px", background: "var(--accent)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6 },
  btnSecondary: { padding: "7px 14px", background: "var(--card)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer", fontSize: 13 },
  iconBtn: { padding: "2px 6px", background: "transparent", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 12 },
};
