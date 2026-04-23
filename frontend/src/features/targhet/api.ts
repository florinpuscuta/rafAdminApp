import { apiFetch } from "../../shared/api";
import type { TgtGrowthList, TgtResponse, TgtScope } from "./types";

export type { TgtScope };

export interface TgtQuery {
  scope: TgtScope;
  /** Anul curent (an realizat). Default: an curent. */
  year?: number;
}

/**
 * GET /api/targhet?scope=adp|sika|sikadp&year=YYYY
 *
 * Procentele de creștere per lună vin din tabelul targhet_growth_pct
 * (editabile prin /api/targhet/growth-pct).
 */
export function getTarghet(q: TgtQuery): Promise<TgtResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  return apiFetch<TgtResponse>(`/api/targhet?${p.toString()}`);
}

export function getGrowthPct(year: number): Promise<TgtGrowthList> {
  return apiFetch<TgtGrowthList>(`/api/targhet/growth-pct?year=${year}`);
}

export function putGrowthPct(
  year: number,
  items: { month: number; pct: number | string }[],
): Promise<TgtGrowthList> {
  return apiFetch<TgtGrowthList>("/api/targhet/growth-pct", {
    method: "PUT",
    body: JSON.stringify({
      year,
      items: items.map((it) => ({ year, month: it.month, pct: String(it.pct) })),
    }),
  });
}
