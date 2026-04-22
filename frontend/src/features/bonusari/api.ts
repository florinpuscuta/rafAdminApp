import { apiFetch } from "../../shared/api";
import type { BonResponse, BonScope } from "./types";

export type { BonScope };

export interface BonQuery {
  scope: BonScope;
  /** Anul calculului. Default: an curent. */
  year?: number;
  /** Ultima lună eligibilă (1..12). Default: luna curentă sau 12. */
  month?: number;
}

/**
 * GET /api/bonusari?scope=adp|sika|sikadp&year=YYYY&month=M
 *
 * Returnează 12 luni × agenți cu bonus + recuperare, totaluri lunare și
 * total global. Conține și regulile (tiers) folosite în calcul, ca UI-ul
 * să afișeze legenda fără duplicare.
 */
export function getBonusari(q: BonQuery): Promise<BonResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  if (q.month != null) p.set("month", String(q.month));
  return apiFetch<BonResponse>(`/api/bonusari?${p.toString()}`);
}
