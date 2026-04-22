import { apiFetch } from "../../shared/api";
import type { PrognozaResponse, PrognozaScope } from "./types";

export type { PrognozaScope };

export interface PrognozaQuery {
  scope: PrognozaScope;
  /** Numarul de luni viitoare de prognozat (1..12). Default 3 pe backend. */
  horizonMonths?: number;
}

/**
 * GET /api/prognoza?scope=adp|sika|sikadp&horizon_months=N
 *
 * Returneaza ultimele 12 luni istoric + N luni forecast, plus breakdown per agent
 * pentru tabelul comparativ.
 */
export function getPrognoza(q: PrognozaQuery): Promise<PrognozaResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.horizonMonths != null) p.set("horizon_months", String(q.horizonMonths));
  return apiFetch<PrognozaResponse>(`/api/prognoza?${p.toString()}`);
}
