import { apiFetch } from "../../shared/api";
import type {
  Agent,
  AgentAlias,
  CreateAgentAliasPayload,
  CreateAgentPayload,
  UnmappedAgentRow,
} from "./types";

export function listAgents(): Promise<Agent[]> {
  return apiFetch<Agent[]>("/api/agents");
}

export function createAgent(payload: CreateAgentPayload): Promise<Agent> {
  return apiFetch<Agent>("/api/agents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listUnmappedAgents(): Promise<UnmappedAgentRow[]> {
  return apiFetch<UnmappedAgentRow[]>("/api/agents/unmapped");
}

export function listAgentAliases(): Promise<AgentAlias[]> {
  return apiFetch<AgentAlias[]>("/api/agents/aliases");
}

export function createAgentAlias(payload: CreateAgentAliasPayload): Promise<AgentAlias> {
  return apiFetch<AgentAlias>("/api/agents/aliases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface MergeAgentsResult {
  primaryId: string;
  mergedCount: number;
  aliasesReassigned: number;
  salesReassigned: number;
  assignmentsReassigned: number;
  assignmentsDeduped: number;
}

export function mergeAgents(
  primaryId: string,
  duplicateIds: string[],
): Promise<MergeAgentsResult> {
  return apiFetch<MergeAgentsResult>("/api/agents/merge", {
    method: "POST",
    body: JSON.stringify({ primaryId, duplicateIds }),
  });
}

export function bulkSetActiveAgents(
  ids: string[],
  active: boolean,
): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>("/api/agents/bulk-set-active", {
    method: "POST",
    body: JSON.stringify({ ids, active }),
  });
}
