import { apiFetch } from "../../shared/api";
import type { Tenant } from "./types";

export function getCurrentTenant(): Promise<Tenant> {
  return apiFetch<Tenant>("/api/tenants/current");
}

export function updateCurrentTenant(name: string): Promise<Tenant> {
  return apiFetch<Tenant>("/api/tenants/current", {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function deactivateCurrentTenant(): Promise<void> {
  return apiFetch<void>("/api/tenants/current", { method: "DELETE" });
}
