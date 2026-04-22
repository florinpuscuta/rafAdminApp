import { apiFetch } from "../../shared/api";
import type { CrossKaFilters, CrossKaResponse } from "./types";

function buildQuery(f: CrossKaFilters): string {
  const q = new URLSearchParams();
  if (f.year != null) q.set("year", String(f.year));
  if (f.months && f.months.length > 0) q.set("months", f.months.join(","));
  if (f.category) q.set("category", f.category);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

/**
 * GET /api/prices/own?year=YYYY&months=1,2,3&category=XYZ
 *
 * Returnează produsele cu dispersie de preț între cele 4 KA. Doar produsele
 * vândute la ≥2 rețele sunt incluse.
 */
export function getCrossKaOwn(filters: CrossKaFilters = {}): Promise<CrossKaResponse> {
  return apiFetch<CrossKaResponse>(`/api/prices/own${buildQuery(filters)}`);
}
