import { apiFetch } from "../../shared/api";
import type { ApiKey, CreateApiKeyResponse } from "./types";

export function listApiKeys(): Promise<ApiKey[]> {
  return apiFetch<ApiKey[]>("/api/api-keys");
}

export function createApiKey(name: string): Promise<CreateApiKeyResponse> {
  return apiFetch<CreateApiKeyResponse>("/api/api-keys", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function revokeApiKey(id: string): Promise<void> {
  return apiFetch<void>(`/api/api-keys/${id}`, { method: "DELETE" });
}
