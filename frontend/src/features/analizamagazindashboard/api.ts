import { apiFetch } from "../../shared/api";
import type {
  AMDClientsResponse,
  AMDDashboardResponse,
  AMDScope,
  AMDStoresResponse,
} from "./types";

const BASE = "/api/analiza-magazin-dashboard";

export function getClients(): Promise<AMDClientsResponse> {
  return apiFetch<AMDClientsResponse>(`${BASE}/clients`);
}

export function getStoresForClient(client: string): Promise<AMDStoresResponse> {
  const p = new URLSearchParams({ client });
  return apiFetch<AMDStoresResponse>(`${BASE}/stores?${p.toString()}`);
}

export function getDashboard(
  scope: AMDScope,
  storeId: string,
  months: number,
): Promise<AMDDashboardResponse> {
  const p = new URLSearchParams({
    scope,
    store_id: storeId,
    months: String(months),
  });
  return apiFetch<AMDDashboardResponse>(`${BASE}?${p.toString()}`);
}
