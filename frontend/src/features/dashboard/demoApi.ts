import { apiFetch } from "../../shared/api";

export interface WipeResult {
  sales: number;
  batches: number;
  assignments: number;
  storeAliases: number;
  agentAliases: number;
  productAliases: number;
  stores: number;
  agents: number;
  products: number;
}

export function wipeTenantData(): Promise<WipeResult> {
  return apiFetch<WipeResult>("/api/demo/wipe", { method: "POST" });
}
