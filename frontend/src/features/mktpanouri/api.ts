/**
 * Panouri & Standuri API — port 1:1 al legacy `/api/panouri/*`.
 * Prefix SaaS: /api/marketing/panouri
 */
import { apiFetch } from "../../shared/api";
import type {
  AddPanelPayload,
  StoreDetailResponse,
  StoresResponse,
  UpdatePanelPayload,
  UUID,
} from "./types";

export function listStores(): Promise<StoresResponse> {
  return apiFetch<StoresResponse>("/api/marketing/panouri/stores");
}

export function getStoreDetail(storeName: string): Promise<StoreDetailResponse> {
  return apiFetch<StoreDetailResponse>(
    `/api/marketing/panouri/store/${encodeURIComponent(storeName)}`,
  );
}

export function addPanel(
  storeName: string, payload: AddPanelPayload,
): Promise<{ ok: boolean }> {
  return apiFetch(
    `/api/marketing/panouri/store/${encodeURIComponent(storeName)}/panel`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function updatePanel(
  panelId: UUID, payload: UpdatePanelPayload,
): Promise<{ ok: boolean }> {
  return apiFetch(`/api/marketing/panouri/panel/${panelId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deletePanel(panelId: UUID): Promise<{ ok: boolean }> {
  return apiFetch(`/api/marketing/panouri/panel/${panelId}`, {
    method: "DELETE",
  });
}
