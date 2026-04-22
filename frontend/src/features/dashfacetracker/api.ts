import { apiFetch } from "../../shared/api";
import type { RaionShareResponse, RaionShareScope } from "./types";

/**
 * GET /api/marketing/facing/raion-share?scope=adp|sika|sikadp&luna=YYYY-MM
 *
 * Pentru scope=sikadp returnează 2 analize (Adeplast + Sika), fiecare excluzând
 * brandurile ecosistemului celuilalt din "Alții".
 */
export function getRaionShare(
  scope: RaionShareScope,
  luna?: string,
): Promise<RaionShareResponse> {
  const p = new URLSearchParams();
  p.set("scope", scope);
  if (luna) p.set("luna", luna);
  return apiFetch<RaionShareResponse>(`/api/marketing/facing/raion-share?${p.toString()}`);
}

export async function getFacingMonths(): Promise<string[]> {
  const r = await apiFetch<{ months: string[] }>("/api/marketing/facing/months");
  return r.months;
}
