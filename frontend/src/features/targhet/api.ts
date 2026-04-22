import { apiFetch } from "../../shared/api";
import type { TgtResponse, TgtScope } from "./types";

export type { TgtScope };

export interface TgtQuery {
  scope: TgtScope;
  /** Anul curent (an realizat). Default: an curent. */
  year?: number;
  /** Procent creștere față de an precedent. Default: 10. */
  targetPct?: number;
}

/**
 * GET /api/targhet?scope=adp|sika|sikadp&year=YYYY&target_pct=10
 *
 * Returnează 12 luni × agenți cu prev / curr / target / gap / achievement%,
 * totaluri pe lună și grand totals.
 */
export function getTarghet(q: TgtQuery): Promise<TgtResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  if (q.targetPct != null) p.set("target_pct", String(q.targetPct));
  return apiFetch<TgtResponse>(`/api/targhet?${p.toString()}`);
}
