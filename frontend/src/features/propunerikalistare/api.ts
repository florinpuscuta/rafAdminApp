import { apiFetch } from "../../shared/api";
import type { PropuneriFilters, PropuneriResponse } from "./types";

function buildQuery(f: PropuneriFilters): string {
  const q = new URLSearchParams();
  if (f.year != null) q.set("year", String(f.year));
  if (f.months && f.months.length > 0) q.set("months", f.months.join(","));
  if (f.company) q.set("company", f.company);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

/**
 * GET /api/prices/propuneri?year=YYYY&months=1,2
 *
 * Returnează, pentru fiecare KA, produsele vândute la alte KA dar nu la acesta.
 */
export function getPropuneriListare(filters: PropuneriFilters = {}): Promise<PropuneriResponse> {
  return apiFetch<PropuneriResponse>(`/api/prices/propuneri${buildQuery(filters)}`);
}
