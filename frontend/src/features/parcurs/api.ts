import { apiFetch } from "../../shared/api";
import type {
  ParcursAgentsResponse,
  ParcursGenerateRequest,
  ParcursResponse,
  ParcursScope,
  ParcursStoresResponse,
} from "./types";

export function getParcursAgents(scope: ParcursScope): Promise<ParcursAgentsResponse> {
  const p = new URLSearchParams({ scope });
  return apiFetch<ParcursAgentsResponse>(`/api/parcurs/agents?${p.toString()}`);
}

export function getParcursStores(
  scope: ParcursScope,
  agent: string,
): Promise<ParcursStoresResponse> {
  const p = new URLSearchParams({ scope, agent });
  return apiFetch<ParcursStoresResponse>(`/api/parcurs/stores?${p.toString()}`);
}

export function generateParcurs(
  req: ParcursGenerateRequest,
): Promise<ParcursResponse> {
  return apiFetch<ParcursResponse>(`/api/parcurs/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}
