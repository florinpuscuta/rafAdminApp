import { apiFetch } from "../../shared/api";
import type { VzResponse } from "./types";

export type VzScope = "adp" | "sika" | "sikadp";

export interface VzQuery {
  scope: VzScope;
  year?: number;
  month?: number;
}

export function getVzLaZi(q: VzQuery): Promise<VzResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  if (q.month != null) p.set("month", String(q.month));
  return apiFetch<VzResponse>(`/api/vz-la-zi?${p.toString()}`);
}
