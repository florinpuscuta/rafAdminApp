import { apiFetch } from "../../shared/api";
import type { AMResponse, AMScope, AMStoresResponse } from "./types";

export type { AMScope };

export function getStores(
  scope: AMScope,
  months: number,
): Promise<AMStoresResponse> {
  const p = new URLSearchParams({ scope, months: String(months) });
  return apiFetch<AMStoresResponse>(`/api/analiza-magazin/stores?${p.toString()}`);
}

export function getAnalizaMagazin(
  scope: AMScope,
  store: string,
  months: number,
): Promise<AMResponse> {
  const p = new URLSearchParams({ scope, store, months: String(months) });
  return apiFetch<AMResponse>(`/api/analiza-magazin?${p.toString()}`);
}
