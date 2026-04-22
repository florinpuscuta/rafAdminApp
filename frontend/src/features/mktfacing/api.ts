/**
 * Facing Tracker API — port 1:1 al `adeplast-dashboard/routes/facing.py`.
 * Prefix: /api/marketing/facing
 */
import { apiFetch } from "../../shared/api";
import type {
  ConfigResponse,
  DashboardResponse,
  EvolutionResponse,
  MonthsResponse,
  OkResponse,
  SaveEntry,
  SaveResponse,
  SnapshotsResponse,
  StoresResponse,
  TreeResponse,
  UUID,
} from "./types";

// ── Config ─────────────────────────────────────────────────────────────────
export function getConfig(): Promise<ConfigResponse> {
  return apiFetch<ConfigResponse>("/api/marketing/facing/config");
}
export function getTree(): Promise<TreeResponse> {
  return apiFetch<TreeResponse>("/api/marketing/facing/tree");
}

// ── Chain × Brand matrix ───────────────────────────────────────────────────
export function saveChainBrands(
  matrix: Record<string, UUID[]>,
): Promise<OkResponse> {
  return apiFetch<OkResponse>("/api/marketing/facing/chain-brands", {
    method: "POST",
    body: JSON.stringify({ matrix }),
  });
}

// ── Raioane CRUD ───────────────────────────────────────────────────────────
export function addRaion(name: string, parentId?: UUID | null): Promise<OkResponse> {
  return apiFetch<OkResponse>("/api/marketing/facing/raioane", {
    method: "POST",
    body: JSON.stringify({ name, parent_id: parentId ?? null }),
  });
}
export function updateRaion(id: UUID, name: string): Promise<OkResponse> {
  return apiFetch<OkResponse>(`/api/marketing/facing/raioane/${id}`, {
    method: "PUT",
    body: JSON.stringify({ name }),
  });
}
export function deleteRaion(id: UUID): Promise<OkResponse> {
  return apiFetch<OkResponse>(`/api/marketing/facing/raioane/${id}`, {
    method: "DELETE",
  });
}

// ── Brands CRUD ────────────────────────────────────────────────────────────
export function addBrand(name: string, color = "#888888"): Promise<OkResponse> {
  return apiFetch<OkResponse>("/api/marketing/facing/brands", {
    method: "POST",
    body: JSON.stringify({ name, color }),
  });
}
export function updateBrand(id: UUID, name: string, color?: string): Promise<OkResponse> {
  return apiFetch<OkResponse>(`/api/marketing/facing/brands/${id}`, {
    method: "PUT",
    body: JSON.stringify({ name, color }),
  });
}
export function deleteBrand(id: UUID): Promise<OkResponse> {
  return apiFetch<OkResponse>(`/api/marketing/facing/brands/${id}`, {
    method: "DELETE",
  });
}

// ── Stores ─────────────────────────────────────────────────────────────────
export function getStores(): Promise<StoresResponse> {
  return apiFetch<StoresResponse>("/api/marketing/facing/stores");
}
export function deleteStoreSnapshots(
  name: string, luna?: string,
): Promise<{ ok: boolean; deleted: number; store: string; luna: string | null }> {
  const params = new URLSearchParams({ name });
  if (luna) params.set("luna", luna);
  return apiFetch(`/api/marketing/facing/store?${params.toString()}`, {
    method: "DELETE",
  });
}

// ── Snapshots ──────────────────────────────────────────────────────────────
export function getSnapshots(store?: string, luna?: string): Promise<SnapshotsResponse> {
  const params = new URLSearchParams();
  if (store) params.set("store", store);
  if (luna) params.set("luna", luna);
  return apiFetch<SnapshotsResponse>(
    `/api/marketing/facing/snapshots?${params.toString()}`,
  );
}
export function saveSnapshots(entries: SaveEntry[]): Promise<SaveResponse> {
  return apiFetch<SaveResponse>("/api/marketing/facing/save", {
    method: "POST",
    body: JSON.stringify({ entries }),
  });
}
export function migrateMonth(luna: string): Promise<OkResponse> {
  return apiFetch<OkResponse>("/api/marketing/facing/migrate-month", {
    method: "POST",
    body: JSON.stringify({ luna }),
  });
}

// ── Evolution & Dashboard ──────────────────────────────────────────────────
export function getEvolution(
  store?: string, raionId?: UUID,
): Promise<EvolutionResponse> {
  const params = new URLSearchParams();
  if (store) params.set("store", store);
  if (raionId) params.set("raion_id", raionId);
  return apiFetch<EvolutionResponse>(
    `/api/marketing/facing/evolution?${params.toString()}`,
  );
}
export function getDashboard(luna?: string): Promise<DashboardResponse> {
  const params = new URLSearchParams();
  if (luna) params.set("luna", luna);
  return apiFetch<DashboardResponse>(
    `/api/marketing/facing/dashboard?${params.toString()}`,
  );
}
export function getMonths(): Promise<MonthsResponse> {
  return apiFetch<MonthsResponse>("/api/marketing/facing/months");
}
