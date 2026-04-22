import { apiFetch, ApiError, getToken } from "../../shared/api";
import type {
  CatalogFolder,
  CatalogFolderDetail,
  CatalogFolderListResponse,
  CatalogPhoto,
  MktCatalogResponse,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** GET /api/marketing/catalog — placeholder compat. */
export function getMktCatalog(): Promise<MktCatalogResponse> {
  return apiFetch<MktCatalogResponse>("/api/marketing/catalog");
}

/** GET /api/marketing/catalog/folders — listă luni cu cover. */
export function listCatalogFolders(): Promise<CatalogFolderListResponse> {
  return apiFetch<CatalogFolderListResponse>("/api/marketing/catalog/folders");
}

/** POST /api/marketing/catalog/folders — creează o lună nouă. */
export function createCatalogFolder(name: string): Promise<CatalogFolder> {
  return apiFetch<CatalogFolder>("/api/marketing/catalog/folders", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

/** DELETE /api/marketing/catalog/folders/{id}. */
export function deleteCatalogFolder(id: string): Promise<void> {
  return apiFetch<void>(`/api/marketing/catalog/folders/${id}`, {
    method: "DELETE",
  });
}

/** GET /api/marketing/catalog/folders/{id}/photos. */
export function getCatalogFolderDetail(
  folderId: string,
): Promise<CatalogFolderDetail> {
  return apiFetch<CatalogFolderDetail>(
    `/api/marketing/catalog/folders/${folderId}/photos`,
  );
}

/** POST /api/marketing/catalog/folders/{id}/photos — upload foto. */
export async function uploadCatalogPhoto(
  folderId: string,
  file: File,
): Promise<CatalogPhoto> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(
    `${API_URL}/api/marketing/catalog/folders/${folderId}/photos`,
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
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        const o = detail as { code?: string; message?: string };
        code = o.code;
        message = o.message ?? message;
      }
    } catch {
      /* non-json */
    }
    throw new ApiError(resp.status, message, code);
  }
  return (await resp.json()) as CatalogPhoto;
}

/** DELETE /api/marketing/catalog/photos/{id}. */
export function deleteCatalogPhoto(id: string): Promise<void> {
  return apiFetch<void>(`/api/marketing/catalog/photos/${id}`, {
    method: "DELETE",
  });
}

/** POST /api/gallery/photos/{id}/rotate?direction=left|right — rotește 90°. */
export function rotateCatalogPhoto(
  id: string, direction: "left" | "right",
): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(
    `/api/gallery/photos/${id}/rotate?direction=${direction}`,
    { method: "POST" },
  );
}
