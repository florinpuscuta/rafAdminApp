import { apiFetch } from "../../shared/api";
import type { KaRetailFilters, KaRetailResponse } from "./types";

function buildQuery(f: KaRetailFilters): string {
  const q = new URLSearchParams();
  if (f.year != null) q.set("year", String(f.year));
  if (f.months && f.months.length > 0) q.set("months", f.months.join(","));
  if (f.category) q.set("category", f.category);
  if (f.limit != null) q.set("limit", String(f.limit));
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

/**
 * GET /api/prices/ka-retail?year=YYYY&months=1,2&category=XYZ&limit=15
 *
 * Top N produse vândute și pe KA și pe Retail (channel='RETAIL' strict),
 * cu prețuri medii și diferență procentuală. Distinct de /ka-vs-tt.
 */
export function getKaRetail(filters: KaRetailFilters = {}): Promise<KaRetailResponse> {
  return apiFetch<KaRetailResponse>(`/api/prices/ka-retail${buildQuery(filters)}`);
}
