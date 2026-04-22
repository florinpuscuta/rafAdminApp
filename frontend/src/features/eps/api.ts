import { apiFetch } from "../../shared/api";
import type { EpsBreakdownResponse, EpsDetailsResponse } from "./types";

export interface EpsDetailsQuery {
  y1: number;
  y2: number;
  months?: number[];
}

function buildQuery(q: EpsDetailsQuery): string {
  const params = new URLSearchParams();
  params.set("y1", String(q.y1));
  params.set("y2", String(q.y2));
  if (q.months && q.months.length > 0) {
    params.set("months", q.months.join(","));
  }
  return params.toString();
}

export function getEpsDetails(q: EpsDetailsQuery): Promise<EpsDetailsResponse> {
  return apiFetch<EpsDetailsResponse>(`/api/eps/details?${buildQuery(q)}`);
}

export function getEpsBreakdown(q: EpsDetailsQuery): Promise<EpsBreakdownResponse> {
  return apiFetch<EpsBreakdownResponse>(`/api/eps/breakdown?${buildQuery(q)}`);
}
