import { apiFetch } from "../../shared/api";
import type { ComenziFaraIndResponse, ComenziFaraIndScope } from "./types";

export type { ComenziFaraIndScope };

export interface ComenziFaraIndQuery {
  scope: ComenziFaraIndScope;
  /** Data raportului (ISO yyyy-mm-dd). Daca lipseste, backend-ul alege ultima. */
  reportDate?: string;
}

/**
 * GET /api/comenzi-fara-ind?scope=adp&report_date=YYYY-MM-DD
 *
 * Intoarce lista comenzilor care nu au IND asociat la data raportului, plus
 * meta (data curenta + alte date disponibile, daca backend-ul le publica).
 */
export function getComenziFaraInd(
  q: ComenziFaraIndQuery,
): Promise<ComenziFaraIndResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.reportDate) p.set("report_date", q.reportDate);
  return apiFetch<ComenziFaraIndResponse>(
    `/api/comenzi-fara-ind?${p.toString()}`,
  );
}
