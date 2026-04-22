import { apiFetch } from "../../shared/api";

export interface StoreAgentMapping {
  id: string;
  source: string;
  clientOriginal: string;
  shipToOriginal: string;
  agentOriginal: string | null;
  codNumeric: string | null;
  cheieFinala: string;
  agentUnificat: string;
  storeId: string | null;
  agentId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface MappingCreatePayload {
  source: string;
  clientOriginal: string;
  shipToOriginal: string;
  agentOriginal?: string | null;
  codNumeric?: string | null;
  cheieFinala: string;
  agentUnificat: string;
}

export type MappingUpdatePayload = Partial<MappingCreatePayload>;

export interface IngestResponse {
  summary: {
    rowsProcessed: number;
    storesCreated: number;
    agentsCreated: number;
    mappingsCreated: number;
    mappingsUpdated: number;
  };
  backfillRowsUpdated: number;
}

export function listMappings(source?: string): Promise<StoreAgentMapping[]> {
  const q = source ? `?source=${encodeURIComponent(source)}` : "";
  return apiFetch<StoreAgentMapping[]>(`/api/mappings${q}`);
}

export function createMapping(
  payload: MappingCreatePayload,
): Promise<StoreAgentMapping> {
  return apiFetch<StoreAgentMapping>("/api/mappings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateMapping(
  id: string,
  payload: MappingUpdatePayload,
): Promise<StoreAgentMapping> {
  return apiFetch<StoreAgentMapping>(`/api/mappings/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteMapping(id: string): Promise<void> {
  return apiFetch<void>(`/api/mappings/${id}`, { method: "DELETE" });
}

export async function uploadMapping(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<IngestResponse>("/api/mappings/upload", {
    method: "POST",
    body: form,
  });
}

export interface UnmappedClientRow {
  clientOriginal: string;
  shipToOriginal: string;
  rawClient: string;
  rowCount: number;
  totalSales: string;
  source: string;
}

export function listUnmapped(
  scope: "adp" | "sika",
): Promise<UnmappedClientRow[]> {
  return apiFetch<UnmappedClientRow[]>(
    `/api/mappings/unmapped?scope=${scope}`,
  );
}
