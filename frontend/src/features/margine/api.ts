import { apiFetch } from "../../shared/api";
import type { MargineResponse, MargineScope } from "./types";

const BASE = "/api/margine";

export function getMargine(
  scope: MargineScope,
  fromYear: number,
  fromMonth: number,
  toYear: number,
  toMonth: number,
): Promise<MargineResponse> {
  const p = new URLSearchParams({
    scope,
    fromYear: String(fromYear),
    fromMonth: String(fromMonth),
    toYear: String(toYear),
    toMonth: String(toMonth),
  });
  return apiFetch<MargineResponse>(`${BASE}?${p.toString()}`);
}
