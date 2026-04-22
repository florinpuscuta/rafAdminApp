import { apiFetch } from "../../shared/api";

export interface PendingPhoto {
  id: string;
  folder_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  caption: string | null;
  uploaded_by_user_id: string | null;
  uploaded_at: string;
  url: string;
  approval_status: string;
  folder_type: string;
  folder_name: string;
}

export interface PendingSummary {
  pending_count: number;
}

export function listPending(): Promise<PendingPhoto[]> {
  return apiFetch<PendingPhoto[]>("/api/gallery/pending");
}

export function getPendingSummary(): Promise<PendingSummary> {
  return apiFetch<PendingSummary>("/api/gallery/pending/summary");
}

export function approvePhoto(id: string): Promise<void> {
  return apiFetch<void>(`/api/gallery/photos/${id}/approve`, { method: "POST" });
}

export function rejectPhoto(id: string): Promise<void> {
  return apiFetch<void>(`/api/gallery/photos/${id}/reject`, { method: "POST" });
}
