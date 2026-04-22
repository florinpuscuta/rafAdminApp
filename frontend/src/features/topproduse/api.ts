import { apiFetch } from "../../shared/api";
import type { TopProduseResponse, TopProduseScope } from "./types";

export type { TopProduseScope };

export interface TopProduseQuery {
  scope: TopProduseScope;
  /** Codul categoriei, ex "EPS", "MU", "UMEDE", "VARSACI". */
  group: string;
  /** Anul curent (Y2). Daca lipseste, backend-ul alege anul curent. */
  year?: number;
  /** Numarul maxim de produse in top. Default 20, max 100. */
  limit?: number;
}

/**
 * GET /api/top-produse?scope=adp|sika|sikadp&group=EPS&year=YYYY&limit=20
 *
 * Returneaza top-N produse dintr-o grupa, sortate descrescator dupa
 * vanzarile anului curent, cu breakdown lunar (12 celule) per produs.
 */
export function getTopProduse(
  q: TopProduseQuery,
): Promise<TopProduseResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  p.set("group", q.group);
  if (q.year != null) p.set("year", String(q.year));
  if (q.limit != null) p.set("limit", String(q.limit));
  return apiFetch<TopProduseResponse>(`/api/top-produse?${p.toString()}`);
}
