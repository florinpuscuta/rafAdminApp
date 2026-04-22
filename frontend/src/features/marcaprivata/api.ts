import { apiFetch } from "../../shared/api";
import type { MarcaPrivataResponse, MarcaPrivataScope } from "./types";

export type { MarcaPrivataScope };

export interface MarcaPrivataQuery {
  scope: MarcaPrivataScope;
  /** Anul curent (Y2). Dacă lipseste, backend-ul alege anul curent. */
  year?: number;
}

/**
 * GET /api/marca-privata?scope=adp&year=YYYY
 *
 * Returneaza vânzările private label pe KA, breakdown lunar Y1 vs Y2 +
 * listă clienți cu totaluri pe ambii ani.
 */
export function getMarcaPrivata(q: MarcaPrivataQuery): Promise<MarcaPrivataResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.year != null) p.set("year", String(q.year));
  return apiFetch<MarcaPrivataResponse>(`/api/marca-privata?${p.toString()}`);
}
