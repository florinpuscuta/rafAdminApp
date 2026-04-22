import { apiFetch } from "../../shared/api";
import type { MortareResponse, MortareScope } from "./types";

export type { MortareScope };

export interface MortareQuery {
  scope: MortareScope;
  /** Anul curent (Y2). Dacă lipseste, backend-ul alege anul curent. */
  year?: number;
}

/**
 * GET /api/mortare?scope=adp&year=YYYY
 *
 * Returneaza vânzările mortare silozuri (vrac) — breakdown lunar Y1 vs Y2
 * + listă produse cu totaluri pe ambii ani.
 */
export function getMortare(q: MortareQuery): Promise<MortareResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  return apiFetch<MortareResponse>(`/api/mortare?${p.toString()}`);
}
