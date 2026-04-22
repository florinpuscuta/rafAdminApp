import { apiFetch } from "../../shared/api";
import type { AnalizaResponse, AnalizaScope } from "./types";

export type { AnalizaScope };

export interface AnalizaQuery {
  scope: AnalizaScope;
  /** Anul curent (Y2). Daca lipseste, backend-ul alege anul curent. */
  year?: number;
}

/**
 * GET /api/analiza-pe-luni?scope=adp|sika|sikadp&year=YYYY
 *
 * Returneaza 12 luni × agenti, cu salesY1 / salesY2 / diff / pct per celula,
 * plus totaluri pe rand (an), pe coloana (luna) si grand total.
 */
export function getAnalizaPeLuni(q: AnalizaQuery): Promise<AnalizaResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  return apiFetch<AnalizaResponse>(`/api/analiza-pe-luni?${p.toString()}`);
}
