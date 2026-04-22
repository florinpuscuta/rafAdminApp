import { apiFetch } from "../../shared/api";
import type { GrupeProduseResponse, GrupeProduseScope } from "./types";

export type { GrupeProduseScope };

export interface GrupeProduseQuery {
  scope: GrupeProduseScope;
  /** Codul categoriei, ex "EPS", "MU", "UMEDE", "VARSACI". */
  group: string;
  /** Anul curent (Y2). Daca lipseste, backend-ul alege anul curent. */
  year?: number;
}

/**
 * GET /api/grupe-produse?scope=adp|sika|sikadp&group=EPS&year=YYYY
 *
 * Returneaza produsele (Y1 vs Y2) dintr-o grupa KA, cu totaluri + lista
 * categoriilor disponibile pentru selectorul din UI.
 */
export function getGrupeProduse(
  q: GrupeProduseQuery,
): Promise<GrupeProduseResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  p.set("group", q.group);
  if (q.year != null) p.set("year", String(q.year));
  return apiFetch<GrupeProduseResponse>(`/api/grupe-produse?${p.toString()}`);
}
