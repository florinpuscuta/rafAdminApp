import { apiFetch, ApiError, getToken } from "../../shared/api";
import type {
  ConcurentaFolderOut,
  ConcurentaPhotosResponse,
  ConcurentaUploadResponse,
  ConcurentaYearResponse,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * GET /api/marketing/concurenta?year=YYYY
 *
 * Port din legacy `fetch('/api/gallery/folders/concurenta')` + filtru
 * `f.name.startsWith(year + '_')` (templates/index.html:12844).
 */
export function getConcurentaYear(year: number): Promise<ConcurentaYearResponse> {
  return apiFetch<ConcurentaYearResponse>(`/api/marketing/concurenta?year=${year}`);
}

/**
 * POST /api/marketing/concurenta/folders
 *
 * Asigură existența folder-ului pentru o lună. Idempotent — legacy
 * crea folderul implicit la primul upload (`os.makedirs(..., exist_ok=True)`).
 */
export function ensureConcurentaFolder(year: number, month: number): Promise<ConcurentaFolderOut> {
  return apiFetch<ConcurentaFolderOut>("/api/marketing/concurenta/folders", {
    method: "POST",
    body: JSON.stringify({ year, month }),
  });
}

/**
 * GET /api/marketing/concurenta/months/{folder_key}/photos
 *
 * Port din legacy `fetch('/api/gallery/concurenta/' + encodeURIComponent(folderKey))`
 * (templates/index.html:12905).
 */
export function getConcurentaPhotos(folderKey: string): Promise<ConcurentaPhotosResponse> {
  return apiFetch<ConcurentaPhotosResponse>(
    `/api/marketing/concurenta/months/${encodeURIComponent(folderKey)}/photos`,
  );
}

/**
 * POST /api/marketing/concurenta/months/{folder_key}/photos
 *
 * Upload multi-file. Oglinda `window.concUpload` (templates/index.html:12958):
 *   const fd = new FormData();
 *   for (const f of files) fd.append('images', f);
 *   fetch(`/api/gallery/concurenta/${folderKey}`, {method:'POST', body:fd})
 */
export async function uploadConcurentaPhotos(
  folderKey: string,
  files: FileList | File[],
): Promise<ConcurentaUploadResponse> {
  const token = getToken();
  const form = new FormData();
  const arr = Array.from(files);
  for (const f of arr) form.append("images", f);
  const resp = await fetch(
    `${API_URL}/api/marketing/concurenta/months/${encodeURIComponent(folderKey)}/photos`,
    {
      method: "POST",
      body: form,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    },
  );
  if (!resp.ok) {
    let code: string | undefined;
    let message = resp.statusText;
    try {
      const d = await resp.json();
      const detail = (d as { detail?: unknown }).detail;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail === "object") {
        const o = detail as { code?: string; message?: string };
        code = o.code;
        message = o.message ?? message;
      }
    } catch {
      /* non-json */
    }
    throw new ApiError(resp.status, message, code);
  }
  return (await resp.json()) as ConcurentaUploadResponse;
}

/**
 * DELETE /api/marketing/concurenta/photos/{photo_id}
 *
 * Port din legacy `window.concDeleteImg` (templates/index.html:12977).
 */
export function deleteConcurentaPhoto(photoId: string): Promise<void> {
  return apiFetch<void>(`/api/marketing/concurenta/photos/${photoId}`, {
    method: "DELETE",
  });
}

/**
 * POST /api/marketing/concurenta/photos/{photo_id}/rotate
 *
 * Port din legacy `window.concRotateImg` (templates/index.html:12984).
 */
export function rotateConcurentaPhoto(photoId: string): Promise<void> {
  return apiFetch<void>(`/api/marketing/concurenta/photos/${photoId}/rotate`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
