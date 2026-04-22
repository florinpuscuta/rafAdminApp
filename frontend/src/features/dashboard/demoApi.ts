import { apiFetch } from "../../shared/api";

export interface SeedResult {
  stores: number;
  agents: number;
  products: number;
  sales: number;
  assignments: number;
}

export function seedDemoData(): Promise<SeedResult> {
  return apiFetch<SeedResult>("/api/demo/seed", { method: "POST" });
}

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
