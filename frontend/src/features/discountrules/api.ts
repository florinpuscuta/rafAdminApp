import { apiFetch } from "../../shared/api";
import type {
  DRBulkUpsertResponse,
  DRMatrixResponse,
  DRRuleIn,
  DRScope,
} from "./types";

const BASE = "/api/discount-rules";

export function getMatrix(scope: DRScope): Promise<DRMatrixResponse> {
  const p = new URLSearchParams({ scope });
  return apiFetch<DRMatrixResponse>(`${BASE}/matrix?${p.toString()}`);
}

export function bulkUpsert(
  scope: DRScope,
  rules: DRRuleIn[],
): Promise<DRBulkUpsertResponse> {
  return apiFetch<DRBulkUpsertResponse>(`${BASE}/bulk-upsert`, {
    method: "POST",
    body: JSON.stringify({ scope, rules }),
  });
}
