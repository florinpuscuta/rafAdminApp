import { apiFetch } from "../../shared/api";
import type { ConsolidatAgentStoresResponse, ConsolidatKaResponse } from "./types";

export interface ConsolidatQuery {
  company: "adeplast" | "sika" | "sikadp";
  y1?: number;
  y2?: number;
  months?: number[];
}

export function getConsolidatKa(q: ConsolidatQuery): Promise<ConsolidatKaResponse> {
  const p = new URLSearchParams();
  p.set("company", q.company);
  if (q.y1 != null) p.set("y1", String(q.y1));
  if (q.y2 != null) p.set("y2", String(q.y2));
  if (q.months && q.months.length > 0) p.set("months", q.months.join(","));
  return apiFetch<ConsolidatKaResponse>(`/api/consolidat/ka?${p.toString()}`);
}

export function getConsolidatAgentStores(
  agentId: string | null,
  q: ConsolidatQuery,
): Promise<ConsolidatAgentStoresResponse> {
  const p = new URLSearchParams();
  p.set("company", q.company);
  if (q.y1 != null) p.set("y1", String(q.y1));
  if (q.y2 != null) p.set("y2", String(q.y2));
  if (q.months && q.months.length > 0) p.set("months", q.months.join(","));
  const seg = agentId ?? "none";
  return apiFetch<ConsolidatAgentStoresResponse>(
    `/api/consolidat/ka/agents/${seg}/stores?${p.toString()}`,
  );
}
