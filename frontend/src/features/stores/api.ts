import { apiFetch } from "../../shared/api";
import type {
  CreateAliasPayload,
  CreateStorePayload,
  Store,
  StoreAlias,
  SuggestionRow,
  UnmappedClientRow,
} from "./types";

export function listStores(): Promise<Store[]> {
  return apiFetch<Store[]>("/api/stores");
}

export function createStore(payload: CreateStorePayload): Promise<Store> {
  return apiFetch<Store>("/api/stores", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listUnmapped(): Promise<UnmappedClientRow[]> {
  return apiFetch<UnmappedClientRow[]>("/api/stores/unmapped");
}

export function listSuggestions(): Promise<SuggestionRow[]> {
  return apiFetch<SuggestionRow[]>("/api/stores/unmapped/suggestions");
}

export function listAliases(): Promise<StoreAlias[]> {
  return apiFetch<StoreAlias[]>("/api/stores/aliases");
}

export function createAlias(payload: CreateAliasPayload): Promise<StoreAlias> {
  return apiFetch<StoreAlias>("/api/stores/aliases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface MergeStoresResult {
  primaryId: string;
  mergedCount: number;
  aliasesReassigned: number;
  salesReassigned: number;
  assignmentsReassigned: number;
  assignmentsDeduped: number;
}

export function mergeStores(
  primaryId: string,
  duplicateIds: string[],
): Promise<MergeStoresResult> {
  return apiFetch<MergeStoresResult>("/api/stores/merge", {
    method: "POST",
    body: JSON.stringify({ primaryId, duplicateIds }),
  });
}

export function bulkSetActiveStores(
  ids: string[],
  active: boolean,
): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>("/api/stores/bulk-set-active", {
    method: "POST",
    body: JSON.stringify({ ids, active }),
  });
}
