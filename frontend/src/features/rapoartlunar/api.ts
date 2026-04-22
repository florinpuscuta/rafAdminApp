import { apiFetch } from "../../shared/api";
import type { RaportLunarResponse } from "./types";

export interface RapoartLunarQuery {
  year?: number;
  month?: number;
}

/**
 * GET /api/rapoarte/lunar?year=YYYY&month=MM
 *
 * Returnează KPI YoY + top clienți + top agenți + chain breakdown pentru
 * luna aleasă. Dacă nu există date, `hasData` e false.
 */
export function getRaportLunar(q: RapoartLunarQuery = {}): Promise<RaportLunarResponse> {
  const p = new URLSearchParams();
  if (q.year != null) p.set("year", String(q.year));
  if (q.month != null) p.set("month", String(q.month));
  const qs = p.toString();
  return apiFetch<RaportLunarResponse>(
    `/api/rapoarte/lunar${qs ? `?${qs}` : ""}`,
  );
}
