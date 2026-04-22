import { apiFetch } from "../../shared/api";

export interface Assignment {
  id: string;
  agentId: string;
  storeId: string;
  createdAt: string;
}

export function listAssignments(): Promise<Assignment[]> {
  return apiFetch<Assignment[]>("/api/agents/assignments");
}

export function assign(agentId: string, storeId: string): Promise<Assignment> {
  return apiFetch<Assignment>("/api/agents/assignments", {
    method: "POST",
    body: JSON.stringify({ agentId, storeId }),
  });
}

export function unassign(agentId: string, storeId: string): Promise<void> {
  return apiFetch<void>("/api/agents/assignments", {
    method: "DELETE",
    body: JSON.stringify({ agentId, storeId }),
  });
}
