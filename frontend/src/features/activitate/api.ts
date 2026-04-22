import { apiFetch } from "../../shared/api";
import type { ActivitateResponse } from "./types";

export type ActivitateScope = "adp" | "sika" | "sikadp";

export interface ActivitateQuery {
  scope: ActivitateScope;
  /** ISO YYYY-MM-DD (inclusive). Dacă lipsește, backend-ul folosește ziua curentă. */
  date?: string;
  /** Dacă e setat împreună cu `dateTo`, face filtrare pe interval. */
  dateFrom?: string;
  dateTo?: string;
}

export function getActivitate(q: ActivitateQuery): Promise<ActivitateResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.date) p.set("date", q.date);
  if (q.dateFrom) p.set("from", q.dateFrom);
  if (q.dateTo) p.set("to", q.dateTo);
  return apiFetch<ActivitateResponse>(`/api/activitate?${p.toString()}`);
}

export interface ActivitateVisitCreate {
  scope: ActivitateScope;
  visitDate: string;           // "YYYY-MM-DD"
  agentId?: string | null;
  storeId?: string | null;
  client?: string | null;
  checkIn?: string | null;
  checkOut?: string | null;
  durationMin?: number | null;
  km?: number | null;
  notes?: string | null;
}

export interface ActivitateVisitCreated {
  id: string;
  visitDate: string;
  agentId: string | null;
  storeId: string | null;
}

export function createVisit(
  payload: ActivitateVisitCreate,
): Promise<ActivitateVisitCreated> {
  return apiFetch<ActivitateVisitCreated>(`/api/activitate/visits`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
