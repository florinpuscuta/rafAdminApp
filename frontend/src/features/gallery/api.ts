import { apiFetch, ApiError, getToken } from "../../shared/api";
import type { FolderType, GalleryFolder, GalleryPhoto } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function listFolders(type?: FolderType): Promise<GalleryFolder[]> {
  const q = type ? `?type=${type}` : "";
  return apiFetch<GalleryFolder[]>(`/api/gallery/folders${q}`);
}

export function createFolder(payload: { type: FolderType; name: string }): Promise<GalleryFolder> {
  return apiFetch<GalleryFolder>("/api/gallery/folders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteFolder(id: string): Promise<void> {
  return apiFetch<void>(`/api/gallery/folders/${id}`, { method: "DELETE" });
}

export function listPhotos(folderId: string): Promise<GalleryPhoto[]> {
  return apiFetch<GalleryPhoto[]>(`/api/gallery/folders/${folderId}/photos`);
}

export async function uploadPhoto(folderId: string, file: File): Promise<GalleryPhoto> {
  const token = getToken();
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(
    `${API_URL}/api/gallery/folders/${folderId}/photos`,
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
    } catch { /* non-json */ }
    throw new ApiError(resp.status, message, code);
  }
  return (await resp.json()) as GalleryPhoto;
}

export function deletePhoto(id: string): Promise<void> {
  return apiFetch<void>(`/api/gallery/photos/${id}`, { method: "DELETE" });
}
