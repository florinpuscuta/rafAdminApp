import { apiFetch } from "../../shared/api";
import type {
  BaselineKind,
  GroupsResponse,
  ProductSearchResponse,
  PromoScope,
  PromoSimResponse,
  PromoStatus,
  PromotionIn,
  PromotionListResponse,
  PromotionOut,
} from "./types";

const BASE = "/api/promotions";

export function listPromotions(
  scope?: PromoScope, status?: PromoStatus,
): Promise<PromotionListResponse> {
  const p = new URLSearchParams();
  if (scope) p.set("scope", scope);
  if (status) p.set("status", status);
  const qs = p.toString();
  return apiFetch<PromotionListResponse>(qs ? `${BASE}?${qs}` : BASE);
}

export function getPromotion(id: string): Promise<PromotionOut> {
  return apiFetch<PromotionOut>(`${BASE}/${id}`);
}

export function createPromotion(payload: PromotionIn): Promise<PromotionOut> {
  return apiFetch<PromotionOut>(BASE, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePromotion(id: string, payload: PromotionIn): Promise<PromotionOut> {
  return apiFetch<PromotionOut>(`${BASE}/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deletePromotion(id: string): Promise<void> {
  return apiFetch<void>(`${BASE}/${id}`, { method: "DELETE" });
}

export function simulatePromotion(
  id: string, baseline: BaselineKind,
): Promise<PromoSimResponse> {
  return apiFetch<PromoSimResponse>(`${BASE}/${id}/simulate?baseline=${baseline}`, {
    method: "POST",
  });
}


export function searchProducts(scope: PromoScope, q: string): Promise<ProductSearchResponse> {
  const p = new URLSearchParams({ scope, q, limit: "500" });
  return apiFetch<ProductSearchResponse>(`${BASE}/products?${p.toString()}`);
}

export function listGroups(scope: PromoScope): Promise<GroupsResponse> {
  const p = new URLSearchParams({ scope });
  return apiFetch<GroupsResponse>(`${BASE}/groups?${p.toString()}`);
}
