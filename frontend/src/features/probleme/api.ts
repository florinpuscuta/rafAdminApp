import { apiFetch } from "../../shared/api";
import type {
  ProblemeResponse,
  ProblemeSaveRequest,
  ProblemeScope,
} from "./types";

export interface ProblemeQuery {
  scope: ProblemeScope;
  /** "YYYY-MM". Dacă lipsește, backend-ul alege luna curentă. */
  period?: string;
}

export function getProbleme(q: ProblemeQuery): Promise<ProblemeResponse> {
  const p = new URLSearchParams();
  p.set("scope", q.scope);
  if (q.period) p.set("period", q.period);
  return apiFetch<ProblemeResponse>(`/api/probleme?${p.toString()}`);
}

export function saveProbleme(
  req: ProblemeSaveRequest,
): Promise<ProblemeResponse> {
  return apiFetch<ProblemeResponse>(`/api/probleme`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}
