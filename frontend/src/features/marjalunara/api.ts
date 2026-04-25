import { apiFetch } from "../../shared/api";
import type { MarjaLunaraResponse, MLScope } from "./types";

const BASE = "/api/marja-lunara";

export function getMarjaLunara(
  scope: MLScope,
  fromYear: number,
  fromMonth: number,
  toYear: number,
  toMonth: number,
): Promise<MarjaLunaraResponse> {
  const p = new URLSearchParams({
    scope,
    fromYear: String(fromYear),
    fromMonth: String(fromMonth),
    toYear: String(toYear),
    toMonth: String(toMonth),
  });
  return apiFetch<MarjaLunaraResponse>(`${BASE}?${p.toString()}`);
}
